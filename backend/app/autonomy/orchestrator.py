"""Bounded, resumable autonomous repository orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.autonomy.context import ContextResolver
from app.autonomy.gateway import ModelCallError
from app.autonomy.models import (
    AnalysisReport,
    AvailabilityProbe,
    AvailabilityStatus,
    CommitAction,
    CommitDecision,
    CriticReview,
    LogicalRole,
    ProviderErrorCategory,
    ReviewerDecision,
    RunContract,
    RunPlan,
    RunState,
    TaskContract,
    TaskKind,
    TaskPlan,
    TaskState,
    VerificationRecord,
)
from app.autonomy.operations import FileOperationApplier, WorkerOutput
from app.autonomy.policy import BoundedExecutionPolicy, PolicyViolation, TaskScope
from app.autonomy.prompts import (
    ceo_plan_prompt,
    commit_authorization_prompt,
    critic_prompt,
    reviewer_prompt,
    worker_prompt,
)
from app.autonomy.registry import ModelRegistry
from app.autonomy.reporting import write_diagnostic_report, write_final_manifest
from app.autonomy.store import RunStore
from app.autonomy.verifier import VerificationEvidence, VerificationRunner
from app.autonomy.workspace import GitWorkspace, WorkspaceError, WorkspaceSnapshot

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredGateway(Protocol):
    """Model gateway boundary used by deterministic controller tests."""

    availability: dict[tuple[str, str], AvailabilityStatus]

    def probe_role(self, *, run_id: str, role: LogicalRole) -> AvailabilityProbe:
        """Probe one model role."""

    def call_structured(
        self,
        *,
        run_id: str,
        role: LogicalRole,
        purpose: str,
        instructions: str,
        input_text: str,
        output_type: type[OutputT],
        allow_model_fallback: bool = True,
        allow_compatibility_fallback: bool = False,
        max_output_tokens: int = 8_000,
    ) -> tuple[OutputT, Any, Any]:
        """Return validated structured output and safe call metadata."""


@dataclass(frozen=True, slots=True)
class ControllerOptions:
    """Bounded execution choices supplied by a human or trusted CLI."""

    max_tasks: int = 10
    allowed_existing_dirty_paths: tuple[str, ...] = ()
    allowed_scope_paths: tuple[str, ...] = ()
    adopt_existing_dirty: bool = False
    enable_independent_critic: bool = True
    push_after_completion: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.max_tasks <= 10:
            raise ValueError("max_tasks must be between 1 and 10")
        if self.adopt_existing_dirty and not self.allowed_existing_dirty_paths:
            raise ValueError("adopting existing work requires explicit dirty paths")


class RunController:
    """Own every state transition, verification decision, and Git commit."""

    def __init__(
        self,
        *,
        repository_root: Path,
        store: RunStore,
        registry: ModelRegistry,
        gateway: StructuredGateway,
        workspace: GitWorkspace | None = None,
        policy: BoundedExecutionPolicy | None = None,
        verification_factory: Callable[[Path], VerificationRunner] | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.store = store
        self.registry = registry
        self.gateway = gateway
        self.workspace = workspace or GitWorkspace(self.repository_root)
        self.policy = policy or BoundedExecutionPolicy()
        self.verification_factory = verification_factory or (
            lambda artifact_directory: VerificationRunner(
                self.repository_root,
                artifact_directory,
            )
        )

    def start(
        self,
        *,
        goal: str,
        continuation_context: str,
        options: ControllerOptions | None = None,
    ) -> RunContract:
        """Create and execute one bounded run."""
        options = options or ControllerOptions()
        initial = self.workspace.snapshot()
        self.workspace.assert_safe_branch(initial.branch)
        expected_dirty = set(options.allowed_existing_dirty_paths)
        if set(initial.changed_files) != expected_dirty:
            raise WorkspaceError(
                "initial dirty paths do not match the explicitly approved set; "
                f"expected={sorted(expected_dirty)} actual={sorted(initial.changed_files)}"
            )

        now = datetime.now(UTC)
        run_uuid = uuid4()
        run_id = str(run_uuid)
        state = RunContract(
            run_id=run_uuid,
            goal=goal,
            repository_root=str(self.repository_root),
            active_branch=initial.branch,
            starting_head=initial.head,
            current_head=initial.head,
            workspace_diff_hash=initial.diff_hash,
            state=RunState.PLANNING,
            initial_dirty_paths=list(initial.changed_files),
            policy_counters=self._policy_payload(),
            created_at=now,
            updated_at=now,
        )
        self._save_state(state)
        self.store.write_json(run_id, "workspace_baseline.json", _snapshot_payload(initial))
        self.store.write_text(run_id, "continuation_map.md", continuation_context)
        self.store.write_json(run_id, "model_registry_snapshot.json", self.registry.snapshot())
        self._event(state, "run_created", goal=goal)

        try:
            probes = self._probe_models(run_id)
            self.store.write_json(
                run_id,
                "model_availability_report.json",
                {"probes": [probe.model_dump(mode="json") for probe in probes]},
            )
            plan = self._create_plan(
                state=state,
                continuation_context=continuation_context,
                options=options,
                initial=initial,
            )
            state.plan = plan
            state.tasks = [
                TaskContract(
                    run_id=run_uuid,
                    plan_task_id=task.task_id,
                    role=task.assigned_role,
                    task_kind=task.task_kind,
                    title=task.title,
                    goal=task.goal,
                    dependencies=task.dependencies,
                    scope_paths=task.scope_paths,
                    acceptance_criteria=task.acceptance_criteria,
                    tests_required=task.tests_required,
                )
                for task in plan.tasks
            ]
            state.task_queue = [task.task_id for task in plan.tasks]
            state.state = RunState.EXECUTING
            self.policy.record_cycle()
            state.policy_counters = self._policy_payload()
            self._save_state(state)
            self.store.write_json(run_id, "ceo_plan.json", plan.model_dump(mode="json"))
            self.store.write_json(
                run_id,
                "task_graph.json",
                {
                    task.task_id: {
                        "dependencies": task.dependencies,
                        "assigned_role": task.assigned_role.value,
                        "scope_paths": task.scope_paths,
                    }
                    for task in plan.tasks
                },
            )
            self._event(state, "plan_accepted", tasks=len(plan.tasks))
            return self._run_loop(state, options)
        except (ModelCallError, PolicyViolation, ValueError, WorkspaceError) as exc:
            return self._block_run(state, f"{type(exc).__name__}: {exc}")

    def resume(self, run_id: str, *, options: ControllerOptions | None = None) -> RunContract:
        """Resume persisted work without repeating completed tasks or calls."""
        state = self.store.load_model(run_id, "run_state.json", RunContract)
        if state.state in {RunState.COMPLETED, RunState.TERMINAL_FAILED}:
            return state
        if any(
            task.state in {TaskState.BLOCKED, TaskState.TERMINAL_FAILED} for task in state.tasks
        ):
            return self._block_run(
                state,
                "a blocked or terminal task requires an explicit revised run",
            )
        self._restore_policy(state.policy_counters)
        options = options or ControllerOptions(
            allowed_existing_dirty_paths=tuple(state.initial_dirty_paths),
            allowed_scope_paths=tuple(
                path
                for task in (state.plan.tasks if state.plan else [])
                for path in task.scope_paths
            ),
            adopt_existing_dirty=bool(state.initial_dirty_paths),
        )
        current = self.workspace.snapshot()
        if current.branch != state.active_branch or current.head != state.current_head:
            return self._block_run(state, "repository branch or HEAD changed during interruption")
        if self.store.exists(run_id, "provider_call_checkpoint.json"):
            checkpoint = self.store.read_json(run_id, "provider_call_checkpoint.json")
            if checkpoint.get("status") == "running":
                return self._block_run(
                    state,
                    "provider call outcome is ambiguous after interruption; no automatic replay",
                )
        if self.store.exists(run_id, "file_apply_checkpoint.json"):
            checkpoint = self.store.read_json(run_id, "file_apply_checkpoint.json")
            if checkpoint.get("status") == "running":
                return self._block_run(
                    state,
                    "file application outcome is ambiguous after interruption",
                )
        if (
            state.active_task_id is not None
            and current.diff_hash != self._active_task(state).checkpoint_diff_hash
        ):
            return self._block_run(state, "repository diff changed after the last task checkpoint")
        state.state = RunState.EXECUTING
        self._save_state(state)
        self._event(state, "run_resumed")
        return self._run_loop(state, options)

    def _probe_models(self, run_id: str) -> list[AvailabilityProbe]:
        probes: list[AvailabilityProbe] = []
        for role in (
            LogicalRole.CEO,
            LogicalRole.REVIEWER,
            LogicalRole.IMPLEMENTATION_WORKER,
            LogicalRole.INDEPENDENT_CRITIC,
        ):
            probe = self.gateway.probe_role(run_id=run_id, role=role)
            if not any(
                item.provider == probe.provider and item.model == probe.model for item in probes
            ):
                probes.append(probe)
        return probes

    def _create_plan(
        self,
        *,
        state: RunContract,
        continuation_context: str,
        options: ControllerOptions,
        initial: WorkspaceSnapshot,
    ) -> RunPlan:
        instructions, payload = ceo_plan_prompt(
            goal=state.goal,
            continuation_context=continuation_context,
            repository_summary={
                "branch": initial.branch,
                "head": initial.head,
                "existing_changed_files": list(initial.changed_files),
                "allowed_scope_paths": list(options.allowed_scope_paths),
                "verification_ids": sorted(
                    self.verification_factory(self.store.run_directory(str(state.run_id))).catalog
                ),
            },
            max_tasks=options.max_tasks,
        )
        plan, call, _ = self.gateway.call_structured(
            run_id=str(state.run_id),
            role=LogicalRole.CEO,
            purpose="ceo_plan",
            instructions=instructions,
            input_text=payload,
            output_type=RunPlan,
            max_output_tokens=6_000,
        )
        self._record_provider_call(state, call.call_id)
        if len(plan.tasks) > options.max_tasks:
            raise ValueError("CEO plan exceeded the configured task limit")
        self._validate_plan(plan, options)
        return plan

    def _validate_plan(self, plan: RunPlan, options: ControllerOptions) -> None:
        allowed_scope = (
            TaskScope(options.allowed_scope_paths, max_changed_files=30)
            if options.allowed_scope_paths
            else None
        )
        catalog = self.verification_factory(self.store.run_directory("_plan_validation")).catalog
        for task in plan.tasks:
            task_scope = TaskScope(tuple(task.scope_paths), max_changed_files=30)
            task_scope.validate(task.scope_paths)
            if allowed_scope is not None:
                allowed_scope.validate(task.scope_paths)
            unknown_tests = set(task.tests_required).difference(catalog)
            if unknown_tests:
                raise ValueError(
                    f"task {task.task_id} requested unknown verification IDs: "
                    f"{', '.join(sorted(unknown_tests))}"
                )

    def _run_loop(self, state: RunContract, options: ControllerOptions) -> RunContract:
        """Iteratively select one eligible task without recursive dispatch."""
        while True:
            if state.state in {RunState.BLOCKED, RunState.TERMINAL_FAILED, RunState.COMPLETED}:
                return state
            task = self._next_task(state)
            if task is None:
                state.state = RunState.COMPLETED
                state.final_state = "all bounded tasks completed and controller-verified"
                state.active_task_id = None
                current = self.workspace.snapshot()
                state.current_head = current.head
                state.workspace_diff_hash = current.diff_hash
                self._save_state(state)
                self._event(state, "run_completed", commits=state.commits_created)
                self._write_reports(state)
                if options.push_after_completion:
                    push = self.workspace.controller_push()
                    self.store.write_json(
                        str(state.run_id),
                        "push_report.json",
                        {
                            "branch": push.branch,
                            "commit": push.commit,
                            "remote": push.remote,
                        },
                    )
                return state
            state.active_task_id = task.task_id
            if task.state is TaskState.PENDING:
                task.state = TaskState.READY
                self._checkpoint_task(state, task)
            try:
                if task.task_kind in {TaskKind.ANALYSIS, TaskKind.REVIEW}:
                    self._execute_analysis(state, task)
                else:
                    self._execute_implementation(state, task, options)
            except (ModelCallError, PolicyViolation, ValueError, WorkspaceError) as exc:
                task.state = TaskState.BLOCKED
                task.blockers.append(f"{type(exc).__name__}: {exc}")
                self._save_state(state)
                return self._block_run(state, task.blockers[-1])

    def _next_task(self, state: RunContract) -> TaskContract | None:
        completed = {
            task.plan_task_id
            for task in state.tasks
            if task.state in {TaskState.COMPLETED, TaskState.SKIPPED}
        }
        for task in state.tasks:
            if task.state in {TaskState.COMPLETED, TaskState.SKIPPED}:
                continue
            if task.state in {TaskState.BLOCKED, TaskState.TERMINAL_FAILED}:
                raise ValueError(
                    f"task {task.plan_task_id or task.title} is terminal and cannot dispatch"
                )
            if set(task.dependencies).issubset(completed):
                return task
        if any(task.state not in {TaskState.COMPLETED, TaskState.SKIPPED} for task in state.tasks):
            raise ValueError("task graph has no eligible task")
        return None

    def _execute_analysis(self, state: RunContract, task: TaskContract) -> None:
        task.state = TaskState.RUNNING
        self._checkpoint_task(state, task)
        context = ContextResolver(self.repository_root).build(task.scope_paths)
        before = self.workspace.snapshot()
        output, call, selection = self.gateway.call_structured(
            run_id=str(state.run_id),
            role=task.role,
            purpose=f"analysis:{task.plan_task_id}",
            instructions=(
                "Perform read-only analysis. Do not propose edits. Return only the structured "
                "analysis report with grounded repository-relative paths."
            ),
            input_text=json.dumps(
                {
                    "goal": task.goal,
                    "acceptance_criteria": task.acceptance_criteria,
                    "context": context.render(),
                },
                indent=2,
            ),
            output_type=AnalysisReport,
            max_output_tokens=5_000,
        )
        self._record_provider_call(state, call.call_id)
        task.assigned_model = selection.spec.model
        after = self.workspace.snapshot()
        if after.diff_hash != before.diff_hash or after.head != before.head:
            raise WorkspaceError("analysis task changed the repository")
        verification = self._verify_task(state, task) if task.tests_required else []
        if any(not item.passed for item in verification):
            raise ValueError("analysis task controller verification failed")
        missing = set(output.inspected_paths).difference(item.path for item in context.files)
        if missing:
            raise ValueError(
                "analysis report cited paths outside its context: " + ", ".join(sorted(missing))
            )
        artifact = self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-analysis.json",
            output.model_dump(mode="json"),
        )
        task.evidence.append(str(artifact))
        task.state = TaskState.COMPLETED
        state.active_task_id = None
        self._checkpoint_task(state, task)
        self._event(state, "analysis_task_completed", task_id=task.plan_task_id)

    def _execute_implementation(
        self,
        state: RunContract,
        task: TaskContract,
        options: ControllerOptions,
    ) -> None:
        plan_task = self._plan_task(state, task)
        before_task = self._task_baseline(state, task)
        task.checkpoint_head = before_task.head
        current = self.workspace.snapshot()
        task.checkpoint_diff_hash = current.diff_hash
        scope = TaskScope(tuple(task.scope_paths), max_changed_files=30)
        verification: list[VerificationEvidence] = []
        output: WorkerOutput
        pending_repair = (
            task.attempt > 0
            and task.repair_attempts >= task.attempt
            and self.store.exists(
                str(state.run_id),
                f"task-{task.plan_task_id}-repair-{task.repair_attempts}.json",
            )
        )
        previous_failure = (
            self.store.read_json(
                str(state.run_id),
                f"task-{task.plan_task_id}-repair-{task.repair_attempts}.json",
            )
            if pending_repair
            else None
        )
        reuse_applied_attempt = (
            task.state is TaskState.VALIDATION_REQUIRED and task.attempt > 0 and not pending_repair
        )
        resume_worker_attempt = (
            task.state in {TaskState.RUNNING, TaskState.REPAIR_REQUIRED}
            and task.attempt > 0
            and not pending_repair
        )

        while True:
            if reuse_applied_attempt:
                output = WorkerOutput.model_validate(
                    self.store.read_json(
                        str(state.run_id),
                        f"task-{task.plan_task_id}-attempt-{task.attempt}-worker.json",
                    )
                )
                after_worker = self.workspace.verify_post_worker(
                    before_task,
                    scope=scope,
                    expected_branch=state.active_branch,
                    expected_head=state.current_head,
                )
                if not any(scope.allows(path) for path in after_worker.changed_files):
                    raise ValueError("implementation task produced no relevant repository diff")
                verification = self._verification_from_records(task)
                if not verification:
                    verification = self._verify_task(state, task)
                reuse_applied_attempt = False
            else:
                task.state = (
                    TaskState.REPAIR_REQUIRED if previous_failure is not None else TaskState.RUNNING
                )
                if not resume_worker_attempt:
                    task.attempt += 1
                resume_worker_attempt = False
                self._checkpoint_task(state, task)
                context = ContextResolver(self.repository_root).build(task.scope_paths)
                instructions, payload = worker_prompt(
                    task=plan_task.model_dump(mode="json"),
                    context_packet=context.render(),
                    previous_failure=previous_failure,
                )
                output, call, selection = self._call_with_escalation(
                    state=state,
                    task=task,
                    purpose=f"worker:{task.plan_task_id}:attempt:{task.attempt}",
                    instructions=instructions,
                    payload=payload,
                    output_type=WorkerOutput,
                )
                self._record_provider_call(state, call.call_id)
                task.assigned_model = selection.spec.model
                artifact = self.store.write_json(
                    str(state.run_id),
                    f"task-{task.plan_task_id}-attempt-{task.attempt}-worker.json",
                    output.model_dump(mode="json"),
                )
                if str(artifact) not in task.evidence:
                    task.evidence.append(str(artifact))
                if output.blockers:
                    raise ValueError("worker reported blockers: " + "; ".join(output.blockers))
                unsupported_reads = set(output.files_read).difference(
                    item.path for item in context.files
                )
                if unsupported_reads:
                    raise ValueError(
                        "worker claimed files outside its supplied context: "
                        + ", ".join(sorted(unsupported_reads))
                    )

                self.store.write_json(
                    str(state.run_id),
                    "file_apply_checkpoint.json",
                    {
                        "status": "running",
                        "task_id": task.plan_task_id,
                        "attempt": task.attempt,
                        "operation_count": len(output.operations),
                    },
                )
                applied = FileOperationApplier(self.repository_root).apply(
                    output.operations,
                    allowed_paths=task.scope_paths,
                )
                self.store.write_json(
                    str(state.run_id),
                    "file_apply_checkpoint.json",
                    {
                        "status": "completed",
                        "task_id": task.plan_task_id,
                        "attempt": task.attempt,
                        "operations": [item.model_dump(mode="json") for item in applied],
                    },
                )
                task.files_touched = sorted(
                    set(task.files_touched).union(item.path for item in applied)
                )
                after_worker = self.workspace.verify_post_worker(
                    before_task,
                    scope=scope,
                    expected_branch=state.active_branch,
                    expected_head=state.current_head,
                )
                scoped_dirty = tuple(
                    path for path in after_worker.changed_files if scope.allows(path)
                )
                if not scoped_dirty:
                    raise ValueError("implementation task produced no relevant repository diff")
                task.state = TaskState.VALIDATION_REQUIRED
                task.checkpoint_diff_hash = after_worker.diff_hash
                state.state = RunState.VALIDATING
                self._save_state(state)
                verification = self._verify_task(state, task)

            if not all(item.passed for item in verification):
                previous_failure = {
                    "failed_checks": [
                        {
                            "identifier": item.identifier,
                            "return_code": item.return_code,
                            "timed_out": item.timed_out,
                            "artifact": item.output_artifact,
                            "output_excerpt": item.output_excerpt,
                        }
                        for item in verification
                        if not item.passed
                    ]
                }
                if task.repair_attempts < task.attempt:
                    self._record_repair(
                        state,
                        task,
                        "verification failed",
                        previous_failure,
                    )
                continue

            intended_paths = tuple(
                path for path in self.workspace.snapshot().changed_files if scope.allows(path)
            )
            diff = self.workspace.review_diff(intended_paths)
            reviewer = self._review(state, task, plan_task, diff, verification, output)
            critic = self._critic(state, task, plan_task, diff, verification, options)
            decision = self._authorize_commit(
                state,
                task,
                plan_task,
                reviewer,
                critic,
                verification,
                list(intended_paths),
            )
            if decision.action is CommitAction.REPAIR:
                previous_failure = {
                    "ceo_required_repairs": decision.required_repairs,
                    "ceo_summary": decision.summary,
                    "reviewer_verdict": reviewer.verdict.value,
                    "reviewer_required_repairs": reviewer.required_repairs,
                }
                if task.repair_attempts < task.attempt:
                    self._record_repair(
                        state,
                        task,
                        "CEO requested evidence-based repair",
                        previous_failure,
                    )
                continue
            if decision.action is CommitAction.BLOCK:
                raise ValueError("CEO blocked commit: " + decision.summary)
            break

        state.state = RunState.COMMITTING
        self._save_state(state)
        commit = self.workspace.controller_commit(
            plan_task.commit_message or f"feat: complete {plan_task.title}",
            intended_paths=intended_paths,
            before=before_task,
            expected_branch=state.active_branch,
            expected_head=state.current_head,
            scope=scope,
            adopt_preexisting_paths=(
                options.adopt_existing_dirty
                and bool(set(intended_paths).intersection(before_task.changed_files))
            ),
        )
        task.commit_sha = commit.commit
        task.files_touched = list(commit.changed_files)
        task.state = TaskState.COMPLETED
        state.commits_created.append(commit.commit)
        state.current_head = commit.commit
        state.active_task_id = None
        state.state = RunState.EXECUTING
        current = self.workspace.snapshot()
        state.workspace_diff_hash = current.diff_hash
        self._save_state(state)
        self._event(
            state,
            "implementation_task_committed",
            task_id=task.plan_task_id,
            commit=commit.commit,
            files=list(commit.changed_files),
        )

    def _task_baseline(
        self,
        state: RunContract,
        task: TaskContract,
    ) -> WorkspaceSnapshot:
        name = f"task-{task.plan_task_id}-workspace-baseline.json"
        run_id = str(state.run_id)
        if self.store.exists(run_id, name):
            payload = self.store.read_json(run_id, name)
            return WorkspaceSnapshot(
                branch=str(payload["branch"]),
                head=str(payload["head"]),
                status=str(payload.get("status", "")),
                changed_files=tuple(payload.get("changed_files", [])),
                staged_files=tuple(payload.get("staged_files", [])),
                diff_hash=str(payload["diff_hash"]),
            )
        baseline = self.workspace.snapshot()
        self.store.write_json(run_id, name, _snapshot_payload(baseline))
        return baseline

    @staticmethod
    def _verification_from_records(
        task: TaskContract,
    ) -> list[VerificationEvidence]:
        return [
            VerificationEvidence(
                identifier=record.identifier,
                command=tuple(record.command),
                working_directory=record.working_directory,
                return_code=record.return_code,
                passed=record.passed,
                timed_out=record.timed_out,
                duration_seconds=record.duration_seconds,
                output_artifact=record.artifact_path,
                output_excerpt=record.output_excerpt,
            )
            for record in task.tests_completed
        ]

    def _record_repair(
        self,
        state: RunContract,
        task: TaskContract,
        reason: str,
        evidence: dict[str, Any],
    ) -> None:
        if not self.policy.allow_repair(str(task.task_id)).allowed:
            raise ValueError(f"{reason} and task repair limit was reached")
        self.policy.record_repair(str(task.task_id))
        task.repair_attempts += 1
        artifact = self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-repair-{task.repair_attempts}.json",
            evidence,
        )
        task.evidence.append(str(artifact))
        state.state = RunState.REPAIRING
        state.policy_counters = self._policy_payload()
        self._save_state(state)
        self._event(
            state,
            "task_repair_requested",
            task_id=task.plan_task_id,
            reason=reason,
            repair_attempt=task.repair_attempts,
        )

    def _call_with_escalation(
        self,
        *,
        state: RunContract,
        task: TaskContract,
        purpose: str,
        instructions: str,
        payload: str,
        output_type: type[OutputT],
    ) -> tuple[OutputT, Any, Any]:
        try:
            return self.gateway.call_structured(
                run_id=str(state.run_id),
                role=task.role,
                purpose=purpose,
                instructions=instructions,
                input_text=payload,
                output_type=output_type,
            )
        except ModelCallError as exc:
            if (
                task.role in {LogicalRole.IMPLEMENTATION_WORKER, LogicalRole.TEST_WORKER}
                and exc.call.error
                and exc.call.error.category
                in {
                    ProviderErrorCategory.MODEL_ACCESS,
                    ProviderErrorCategory.OUTPUT_VALIDATION,
                }
                and self.policy.allow_escalation("luna", "terra").allowed
            ):
                self.policy.record_escalation("luna", "terra")
                self.gateway.availability[(exc.call.provider, exc.call.model)] = (
                    AvailabilityStatus.UNAVAILABLE
                )
                state.policy_counters = self._policy_payload()
                self._save_state(state)
                self._event(
                    state,
                    "model_escalated",
                    task_id=task.plan_task_id,
                    from_model=exc.call.model,
                    to_role="terra",
                )
                return self.gateway.call_structured(
                    run_id=str(state.run_id),
                    role=task.role,
                    purpose=f"{purpose}:escalated",
                    instructions=instructions,
                    input_text=payload,
                    output_type=output_type,
                )
            raise

    def _verify_task(
        self,
        state: RunContract,
        task: TaskContract,
    ) -> list[VerificationEvidence]:
        attempt_label = f"attempt-{task.attempt}" if task.attempt else "analysis"
        artifact_directory = (
            self.store.run_directory(str(state.run_id))
            / f"task-{task.plan_task_id}-{attempt_label}"
        )
        runner = self.verification_factory(artifact_directory)
        evidence = runner.run(task.tests_required)
        task.tests_completed = [
            VerificationRecord(
                identifier=item.identifier,
                command=list(item.command),
                working_directory=item.working_directory,
                passed=item.passed,
                return_code=item.return_code,
                timed_out=item.timed_out,
                duration_seconds=item.duration_seconds,
                artifact_path=item.output_artifact,
                output_excerpt=item.output_excerpt,
            )
            for item in evidence
        ]
        self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-{attempt_label}-verification.json",
            {"checks": [_verification_payload(item) for item in evidence]},
        )
        self._save_state(state)
        return evidence

    def _review(
        self,
        state: RunContract,
        task: TaskContract,
        plan_task: TaskPlan,
        diff: str,
        verification: list[VerificationEvidence],
        worker_output: WorkerOutput,
    ) -> ReviewerDecision:
        instructions, payload = reviewer_prompt(
            task=plan_task.model_dump(mode="json"),
            diff_summary=diff,
            verification=[_verification_payload(item) for item in verification],
            worker_evidence=worker_output.model_dump(mode="json"),
        )
        review, call, _ = self.gateway.call_structured(
            run_id=str(state.run_id),
            role=LogicalRole.REVIEWER,
            purpose=f"review:{task.plan_task_id}",
            instructions=instructions,
            input_text=payload,
            output_type=ReviewerDecision,
            max_output_tokens=2_000,
        )
        self._record_provider_call(state, call.call_id)
        self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-review.json",
            review.model_dump(mode="json"),
        )
        return review

    def _critic(
        self,
        state: RunContract,
        task: TaskContract,
        plan_task: TaskPlan,
        diff: str,
        verification: list[VerificationEvidence],
        options: ControllerOptions,
    ) -> CriticReview | None:
        if not options.enable_independent_critic:
            return None
        spec = self.registry.get(LogicalRole.INDEPENDENT_CRITIC)
        status = self.gateway.availability.get((spec.provider, spec.model))
        if status is not AvailabilityStatus.AVAILABLE:
            self._event(
                state,
                "independent_critic_skipped",
                task_id=task.plan_task_id,
                reason="primary Kimi model unavailable",
            )
            return None
        if not self.policy.allow_independent_critic().allowed:
            return None
        self.policy.record_independent_critic()
        state.policy_counters = self._policy_payload()
        instructions, payload = critic_prompt(
            task=plan_task.model_dump(mode="json"),
            diff_summary=diff,
            verification=[_verification_payload(item) for item in verification],
        )
        review, call, _ = self.gateway.call_structured(
            run_id=str(state.run_id),
            role=LogicalRole.INDEPENDENT_CRITIC,
            purpose=f"critic:{task.plan_task_id}",
            instructions=instructions,
            input_text=payload,
            output_type=CriticReview,
            allow_model_fallback=False,
            max_output_tokens=3_000,
        )
        self._record_provider_call(state, call.call_id)
        self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-critic.json",
            review.model_dump(mode="json"),
        )
        return review

    def _authorize_commit(
        self,
        state: RunContract,
        task: TaskContract,
        plan_task: TaskPlan,
        reviewer: ReviewerDecision,
        critic: CriticReview | None,
        verification: list[VerificationEvidence],
        changed_files: list[str],
    ) -> CommitDecision:
        instructions, payload = commit_authorization_prompt(
            goal=state.goal,
            task=plan_task.model_dump(mode="json"),
            reviewer=reviewer.model_dump(mode="json"),
            critic=critic.model_dump(mode="json") if critic else None,
            verification=[_verification_payload(item) for item in verification],
            changed_files=changed_files,
        )
        decision, call, _ = self.gateway.call_structured(
            run_id=str(state.run_id),
            role=LogicalRole.CEO,
            purpose=f"commit_authorization:{task.plan_task_id}",
            instructions=instructions,
            input_text=payload,
            output_type=CommitDecision,
            max_output_tokens=2_000,
        )
        self._record_provider_call(state, call.call_id)
        self.store.write_json(
            str(state.run_id),
            f"task-{task.plan_task_id}-commit-decision.json",
            decision.model_dump(mode="json"),
        )
        return decision

    def _checkpoint_task(self, state: RunContract, task: TaskContract) -> None:
        snapshot = self.workspace.snapshot()
        task.checkpoint_head = snapshot.head
        task.checkpoint_diff_hash = snapshot.diff_hash
        state.current_head = snapshot.head
        state.workspace_diff_hash = snapshot.diff_hash
        state.updated_at = datetime.now(UTC)
        self._save_state(state)
        self._event(
            state,
            "task_state_changed",
            task_id=task.plan_task_id,
            task_state=task.state.value,
        )

    def _save_state(self, state: RunContract) -> None:
        state.updated_at = datetime.now(UTC)
        state.policy_counters = self._policy_payload()
        self.store.save_model(str(state.run_id), "run_state.json", state)

    @staticmethod
    def _record_provider_call(state: RunContract, call_id: UUID) -> None:
        if call_id not in state.provider_calls:
            state.provider_calls.append(call_id)

    def _event(self, state: RunContract, event: str, **details: Any) -> None:
        payload = {"event": event, "run_state": state.state.value, **details}
        self.store.append_event(
            str(state.run_id),
            payload,
        )
        self.store.append_records(
            str(state.run_id),
            "task_execution_log.jsonl",
            [{"timestamp": datetime.now(UTC).isoformat(), **payload}],
        )

    def _block_run(self, state: RunContract, reason: str) -> RunContract:
        state.state = RunState.BLOCKED
        if reason not in state.blockers:
            state.blockers.append(reason)
        state.final_state = f"blocked: {reason}"
        self._save_state(state)
        self._event(state, "run_blocked", reason=reason)
        self._write_reports(state)
        return state

    def _plan_task(self, state: RunContract, task: TaskContract) -> TaskPlan:
        if state.plan is None or task.plan_task_id is None:
            raise ValueError("task has no persisted CEO plan")
        for candidate in state.plan.tasks:
            if candidate.task_id == task.plan_task_id:
                return candidate
        raise ValueError(f"plan task not found: {task.plan_task_id}")

    @staticmethod
    def _active_task(state: RunContract) -> TaskContract:
        for task in state.tasks:
            if task.task_id == state.active_task_id:
                return task
        raise ValueError("active task is missing")

    def _policy_payload(self) -> dict[str, Any]:
        return {
            "max_replans": self.policy.max_replans,
            "max_cycles": self.policy.max_cycles,
            "max_repairs_per_task": self.policy.max_repairs_per_task,
            "max_luna_to_terra_escalations": self.policy.max_luna_to_terra_escalations,
            "max_terra_to_sol_escalations": self.policy.max_terra_to_sol_escalations,
            "max_independent_critiques": self.policy.max_independent_critiques,
            "max_identical_retries": self.policy.max_identical_retries,
            "replan_count": self.policy.replan_count,
            "cycle_count": self.policy.cycle_count,
            "repairs_by_task": dict(self.policy.repairs_by_task),
            "escalations": {
                f"{source}->{target}": count
                for (source, target), count in self.policy.escalations.items()
            },
            "independent_critiques": self.policy.independent_critiques,
        }

    def _restore_policy(self, payload: dict[str, Any]) -> None:
        """Restore persisted counters so interruption cannot reset bounded limits."""
        if not payload:
            return
        for field in (
            "max_replans",
            "max_cycles",
            "max_repairs_per_task",
            "max_luna_to_terra_escalations",
            "max_terra_to_sol_escalations",
            "max_independent_critiques",
            "max_identical_retries",
        ):
            if field in payload:
                setattr(self.policy, field, int(payload[field]))
        self.policy.replan_count = int(payload.get("replan_count", 0))
        self.policy.cycle_count = int(payload.get("cycle_count", 0))
        self.policy.repairs_by_task = {
            str(task_id): int(count)
            for task_id, count in dict(payload.get("repairs_by_task", {})).items()
        }
        restored_escalations: dict[tuple[str, str], int] = {}
        for route, count in dict(payload.get("escalations", {})).items():
            source, separator, target = str(route).partition("->")
            if separator:
                restored_escalations[(source, target)] = int(count)
        self.policy.escalations = restored_escalations
        self.policy.independent_critiques = int(payload.get("independent_critiques", 0))

    def _write_reports(self, state: RunContract) -> None:
        run_id = str(state.run_id)
        directory = self.store.run_directory(run_id)
        availability: list[dict[str, Any]] = []
        if self.store.exists(run_id, "model_availability_report.json"):
            payload = self.store.read_json(run_id, "model_availability_report.json")
            availability = list(payload.get("probes", []))
        write_final_manifest(
            directory,
            state=state,
            registry_snapshot=self.registry.snapshot(),
            availability=availability,
        )
        self.store.write_json(
            run_id,
            "test_report.json",
            {
                "tasks": [
                    {
                        "task_id": task.plan_task_id,
                        "checks": [check.model_dump(mode="json") for check in task.tests_completed],
                    }
                    for task in state.tasks
                ]
            },
        )
        self.store.write_json(
            run_id,
            "commit_report.json",
            {
                "commits": state.commits_created,
                "controller_owned": True,
                "active_branch": state.active_branch,
                "current_head": state.current_head,
            },
        )
        self.store.write_json(
            run_id,
            "provider_usage.json",
            _provider_usage_payload(directory / "provider_calls.jsonl"),
        )
        write_diagnostic_report(
            directory,
            title="CareerOS Autonomous Run",
            summary=state.final_state or state.state.value,
            sections={
                "Goal": state.goal,
                "Tasks": [
                    f"{task.plan_task_id or task.title}: {task.state.value}" for task in state.tasks
                ],
                "Commits": state.commits_created,
                "Blockers": state.blockers,
                "Human Gates": [
                    "Merging to main, deployment, publishing, communication, applications, "
                    "production data changes, and irreversible external actions remain manual."
                ],
            },
        )


def _snapshot_payload(snapshot: WorkspaceSnapshot) -> dict[str, Any]:
    return {
        "branch": snapshot.branch,
        "head": snapshot.head,
        "status": snapshot.status,
        "changed_files": list(snapshot.changed_files),
        "staged_files": list(snapshot.staged_files),
        "diff_hash": snapshot.diff_hash,
    }


def _verification_payload(evidence: VerificationEvidence) -> dict[str, Any]:
    return {
        "identifier": evidence.identifier,
        "command": list(evidence.command),
        "working_directory": evidence.working_directory,
        "return_code": evidence.return_code,
        "passed": evidence.passed,
        "timed_out": evidence.timed_out,
        "duration_seconds": evidence.duration_seconds,
        "output_artifact": evidence.output_artifact,
        "output_excerpt": evidence.output_excerpt,
    }


def _provider_usage_payload(path: Path) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    calls.append(payload)
    by_model: dict[str, dict[str, Any]] = {}
    for call in calls:
        key = f"{call.get('provider')}:{call.get('model')}"
        summary = by_model.setdefault(
            key,
            {
                "provider": call.get("provider"),
                "model": call.get("model"),
                "calls": 0,
                "attempts": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reported_cost_usd": 0.0,
            },
        )
        summary["calls"] += 1
        summary["attempts"] += int(call.get("attempts") or 0)
        usage = call.get("usage") or {}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            summary[field] += int(usage.get(field) or 0)
        summary["reported_cost_usd"] += float(usage.get("reported_cost_usd") or 0.0)
    return {
        "call_count": len(calls),
        "models": list(by_model.values()),
        "reported_cost_note": (
            "Cost is included only when explicitly reported by the provider; "
            "zero is not an estimate."
        ),
    }


__all__ = ["ControllerOptions", "RunController"]
