"""End-to-end offline tests for the bounded run controller."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.autonomy.models import (
    AnalysisReport,
    AvailabilityProbe,
    AvailabilityStatus,
    CommitAction,
    CommitDecision,
    LogicalRole,
    ModelSelection,
    ProviderCall,
    ProviderCallState,
    ReviewerDecision,
    ReviewVerdict,
    RunContract,
    RunPlan,
    RunState,
    TaskContract,
    TaskKind,
    TaskPlan,
    TaskState,
)
from app.autonomy.operations import FileOperation, FileOperationKind, WorkerOutput
from app.autonomy.orchestrator import ControllerOptions, RunController
from app.autonomy.registry import ModelRegistry, RegistrySettings
from app.autonomy.store import RunStore
from app.autonomy.verifier import VerificationCommand, VerificationEvidence
from app.autonomy.workspace import GitWorkspace


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class FakeVerificationRunner:
    def __init__(self, artifact_directory: Path, outcomes: list[bool]) -> None:
        self.artifact_directory = artifact_directory
        self.outcomes = outcomes
        self.catalog = {
            "fake-test": VerificationCommand(
                "fake-test",
                ".",
                ("fake-test",),
                10,
            )
        }

    def run(self, identifiers: list[str]) -> list[VerificationEvidence]:
        outcome = self.outcomes.pop(0)
        artifact = self.artifact_directory / "verification-fake-test.log"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("pass" if outcome else "fail", encoding="utf-8")
        return [
            VerificationEvidence(
                identifier="fake-test",
                command=("fake-test",),
                working_directory=".",
                return_code=0 if outcome else 1,
                passed=outcome,
                timed_out=False,
                duration_seconds=0.01,
                output_artifact=str(artifact),
            )
        ]


class FakeGateway:
    def __init__(
        self,
        registry: ModelRegistry,
        *,
        worker_outputs: list[WorkerOutput],
        plan: RunPlan | None = None,
        commit_decisions: list[CommitDecision] | None = None,
        analysis_report: AnalysisReport | None = None,
    ) -> None:
        self.registry = registry
        self.worker_outputs = worker_outputs
        self.plan = plan or _plan()
        self.commit_decisions = commit_decisions or []
        self.analysis_report = analysis_report
        self.availability: dict[tuple[str, str], AvailabilityStatus] = {}
        self.purposes: list[str] = []

    def probe_role(self, *, run_id: str, role: LogicalRole) -> AvailabilityProbe:
        del run_id
        spec = self.registry.get(role)
        self.availability[(spec.provider, spec.model)] = AvailabilityStatus.AVAILABLE
        return AvailabilityProbe(
            provider=spec.provider,
            model=spec.model,
            status=AvailabilityStatus.AVAILABLE,
            authenticated=True,
            endpoint=spec.endpoint,
            endpoint_reachable=True,
            tool_calling=spec.capabilities.tool_calling,
            structured_output=spec.capabilities.structured_output,
            duration_ms=1,
        )

    def call_structured(
        self,
        *,
        run_id: str,
        role: LogicalRole,
        purpose: str,
        instructions: str,
        input_text: str,
        output_type: type[Any],
        allow_model_fallback: bool = True,
        allow_compatibility_fallback: bool = False,
        max_output_tokens: int = 8_000,
    ) -> tuple[Any, ProviderCall, ModelSelection]:
        del run_id, instructions, input_text, output_type
        del allow_model_fallback, allow_compatibility_fallback, max_output_tokens
        self.purposes.append(purpose)
        if purpose == "ceo_plan":
            output: Any = self.plan
        elif purpose.startswith("analysis:"):
            if self.analysis_report is None:
                raise AssertionError("analysis report fixture was not configured")
            output = self.analysis_report
        elif purpose.startswith("worker:"):
            output = self.worker_outputs.pop(0)
        elif purpose.startswith("review:"):
            output = ReviewerDecision(
                verdict=ReviewVerdict.APPROVE,
                summary="The diff and controller test evidence satisfy the task.",
            )
        elif purpose.startswith("commit_authorization:"):
            output = (
                self.commit_decisions.pop(0)
                if self.commit_decisions
                else CommitDecision(
                    action=CommitAction.AUTHORIZE,
                    summary="The controller may create the bounded commit.",
                )
            )
        else:  # pragma: no cover - catches accidental new call stages
            raise AssertionError(f"unexpected purpose: {purpose}")
        selection = self.registry.resolve(role)
        call = ProviderCall(
            call_id=uuid4(),
            role=role,
            provider=selection.spec.provider,
            model=selection.spec.model,
            purpose=purpose,
            state=ProviderCallState.SUCCEEDED,
            attempts=1,
            structured_output=output.model_dump(mode="json"),
            duration_ms=1,
        )
        return output, call, selection


def _plan() -> RunPlan:
    return RunPlan(
        summary="Create and verify one bounded source file.",
        tasks=[
            TaskPlan(
                task_id="add-feature",
                task_kind=TaskKind.IMPLEMENTATION,
                title="Add a bounded feature file",
                goal="Create one source file and verify it through the controller.",
                assigned_role=LogicalRole.IMPLEMENTATION_WORKER,
                scope_paths=["feature.txt"],
                acceptance_criteria=["feature.txt contains the verified implementation"],
                tests_required=["fake-test"],
                commit_message="feat: add bounded autonomous feature",
            )
        ],
        stop_conditions=["Stop after the verified controller commit."],
    )


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "autonomy/test")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Autonomy Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    git(root, "add", "--", "README.md")
    git(root, "commit", "-m", "initial")
    return root


def _controller(
    root: Path,
    tmp_path: Path,
    gateway: FakeGateway,
    outcomes: list[bool],
) -> RunController:
    return RunController(
        repository_root=root,
        store=RunStore(tmp_path / "artifacts"),
        registry=gateway.registry,
        gateway=gateway,
        workspace=GitWorkspace(root),
        verification_factory=lambda directory: FakeVerificationRunner(directory, outcomes),
    )


def test_successful_run_commits_only_after_controller_verification(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Created the scoped implementation.",
                files_read=[],
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        content="verified\n",
                    )
                ],
                evidence=["The requested file content is explicit."],
            )
        ],
    )
    controller = _controller(root, tmp_path, gateway, [True])

    result = controller.start(
        goal="Create one verified bounded feature.",
        continuation_context="No earlier work is required.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.COMPLETED
    assert result.tasks[0].state is TaskState.COMPLETED
    assert result.tasks[0].commit_sha == git(root, "rev-parse", "HEAD")
    assert git(root, "show", "--format=%s", "-s") == "feat: add bounded autonomous feature"
    assert (root / "feature.txt").read_text(encoding="utf-8") == "verified\n"
    assert gateway.purposes == [
        "ceo_plan",
        "worker:add-feature:attempt:1",
        "review:add-feature",
        "commit_authorization:add-feature",
    ]


def test_analysis_task_requires_grounded_report_and_never_commits(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    starting_head = git(root, "rev-parse", "HEAD")
    plan = RunPlan(
        summary="Inspect one bounded source file without editing it.",
        tasks=[
            TaskPlan(
                task_id="inspect-readme",
                task_kind=TaskKind.ANALYSIS,
                title="Inspect the repository readme",
                goal="Produce grounded read-only evidence about the repository.",
                assigned_role=LogicalRole.RESEARCH_WORKER,
                scope_paths=["README.md"],
                acceptance_criteria=["The report cites the supplied README.md file."],
                tests_required=["fake-test"],
            )
        ],
        stop_conditions=["Stop after controller verification of the report."],
    )
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(
        registry,
        worker_outputs=[],
        plan=plan,
        analysis_report=AnalysisReport(
            inspected_paths=["README.md"],
            commands_run=[],
            grounded_findings=["README.md contains the initial repository marker."],
            unknown_or_unverified=[],
            recommended_next_step="Keep the implementation task separate.",
        ),
    )
    controller = _controller(root, tmp_path, gateway, [True])

    result = controller.start(
        goal="Run one verified read-only analysis.",
        continuation_context="No repository edit is permitted.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("README.md",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.COMPLETED
    assert result.tasks[0].state is TaskState.COMPLETED
    assert result.tasks[0].commit_sha is None
    assert result.tasks[0].tests_completed[0].passed is True
    assert git(root, "rev-parse", "HEAD") == starting_head


def test_failed_verification_triggers_one_bounded_repair(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Initial implementation.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        content="first\n",
                    )
                ],
            ),
            WorkerOutput(
                summary="Repaired implementation.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        expected_sha256=(
                            "b640e840b19d378660b32fb51ae18d67dccb4a8596a29e7bd72c1b2ae5928f41"
                        ),
                        content="verified\n",
                    )
                ],
            ),
        ],
    )
    controller = _controller(root, tmp_path, gateway, [False, True])

    result = controller.start(
        goal="Repair one bounded feature after a deterministic test failure.",
        continuation_context="The controller must use the changed failure evidence.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.COMPLETED
    assert result.tasks[0].repair_attempts == 1
    assert gateway.purposes.count("worker:add-feature:attempt:1") == 1
    assert gateway.purposes.count("worker:add-feature:attempt:2") == 1


def test_ceo_repair_decision_uses_the_same_bounded_repair_budget(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    first = "draft\n"
    gateway = FakeGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Initial verified draft.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        content=first,
                    )
                ],
            ),
            WorkerOutput(
                summary="Applied the CEO's evidence-based repair.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        expected_sha256=hashlib.sha256(first.encode()).hexdigest(),
                        content="verified\n",
                    )
                ],
            ),
        ],
        commit_decisions=[
            CommitDecision(
                action=CommitAction.REPAIR,
                summary="One acceptance detail still needs correction.",
                required_repairs=["Replace the draft marker with the verified content."],
            ),
            CommitDecision(
                action=CommitAction.AUTHORIZE,
                summary="The repaired implementation is verified.",
            ),
        ],
    )
    controller = _controller(root, tmp_path, gateway, [True, True])

    result = controller.start(
        goal="Allow one bounded CEO-requested repair.",
        continuation_context="The controller must own the repair counter.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.COMPLETED
    assert result.tasks[0].repair_attempts == 1
    assert result.tasks[0].attempt == 2
    assert (root / "feature.txt").read_text(encoding="utf-8") == "verified\n"


def test_no_diff_implementation_is_blocked_without_commit(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    starting_head = git(root, "rev-parse", "HEAD")
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(
        registry,
        worker_outputs=[WorkerOutput(summary="No change was proposed.")],
    )
    controller = _controller(root, tmp_path, gateway, [True])

    result = controller.start(
        goal="Attempt one implementation.",
        continuation_context="An implementation must produce a relevant diff.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.BLOCKED
    assert result.tasks[0].state is TaskState.BLOCKED
    assert result.commits_created == []
    assert git(root, "rev-parse", "HEAD") == starting_head


def test_read_only_context_can_be_inspected_but_not_edited(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    plan = _plan()
    plan.tasks[0].context_paths = ["README.md"]
    gateway = FakeGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Attempted to edit a read-only dependency.",
                files_read=["README.md"],
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="README.md",
                        expected_sha256=hashlib.sha256(b"initial\n").hexdigest(),
                        content="not allowed\n",
                    )
                ],
            )
        ],
        plan=plan,
    )
    controller = _controller(root, tmp_path, gateway, [True])

    result = controller.start(
        goal="Keep context files read-only.",
        continuation_context="README.md is evidence, not writable scope.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            allowed_context_paths=("README.md",),
            enable_independent_critic=False,
        ),
    )

    assert result.state is RunState.BLOCKED
    assert "outside task scope" in result.blockers[-1]
    assert (root / "README.md").read_text(encoding="utf-8") == "initial\n"


def test_completed_run_resume_does_not_repeat_models_or_tasks(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Create file.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        content="done\n",
                    )
                ],
            )
        ],
    )
    controller = _controller(root, tmp_path, gateway, [True])
    result = controller.start(
        goal="Create one resumable feature.",
        continuation_context="Completed work must not repeat.",
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )
    calls_before_resume = list(gateway.purposes)

    resumed = controller.resume(str(result.run_id))

    assert resumed.state is RunState.COMPLETED
    assert gateway.purposes == calls_before_resume


def test_resume_after_verified_diff_does_not_repeat_worker_call(tmp_path: Path) -> None:
    class InterruptBeforeReviewGateway(FakeGateway):
        def call_structured(self, **kwargs: Any) -> tuple[Any, ProviderCall, ModelSelection]:
            if str(kwargs["purpose"]).startswith("review:"):
                raise RuntimeError("simulated controller interruption")
            return super().call_structured(**kwargs)

    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    first_gateway = InterruptBeforeReviewGateway(
        registry,
        worker_outputs=[
            WorkerOutput(
                summary="Create resumable work.",
                operations=[
                    FileOperation(
                        kind=FileOperationKind.WRITE,
                        path="feature.txt",
                        content="resumable\n",
                    )
                ],
            )
        ],
    )
    first_controller = _controller(root, tmp_path, first_gateway, [True])

    with pytest.raises(RuntimeError, match="simulated controller interruption"):
        first_controller.start(
            goal="Resume after deterministic verification.",
            continuation_context="Do not repeat a successful worker call.",
            options=ControllerOptions(
                max_tasks=1,
                allowed_scope_paths=("feature.txt",),
                enable_independent_critic=False,
            ),
        )

    run_directories = [
        item
        for item in (tmp_path / "artifacts").iterdir()
        if item.is_dir() and not item.name.startswith("_")
    ]
    assert len(run_directories) == 1
    run_id = run_directories[0].name
    second_gateway = FakeGateway(registry, worker_outputs=[])
    second_controller = _controller(root, tmp_path, second_gateway, [])

    resumed = second_controller.resume(
        run_id,
        options=ControllerOptions(
            max_tasks=1,
            allowed_scope_paths=("feature.txt",),
            enable_independent_critic=False,
        ),
    )

    assert resumed.state is RunState.COMPLETED
    assert all(not purpose.startswith("worker:") for purpose in second_gateway.purposes)
    assert second_gateway.purposes == [
        "review:add-feature",
        "commit_authorization:add-feature",
    ]


def test_ambiguous_provider_checkpoint_blocks_resume_without_model_call(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(registry, worker_outputs=[])
    store = RunStore(tmp_path / "artifacts")
    state = RunContract(
        goal="Resume safely.",
        repository_root=str(root),
        active_branch="autonomy/test",
        starting_head=git(root, "rev-parse", "HEAD"),
        current_head=git(root, "rev-parse", "HEAD"),
        workspace_diff_hash=GitWorkspace(root).snapshot().diff_hash,
        state=RunState.EXECUTING,
    )
    store.save_model(str(state.run_id), "run_state.json", state)
    store.write_json(
        str(state.run_id),
        "provider_call_checkpoint.json",
        {"status": "running", "purpose": "worker"},
    )
    controller = RunController(
        repository_root=root,
        store=store,
        registry=registry,
        gateway=gateway,
        workspace=GitWorkspace(root),
    )

    resumed = controller.resume(str(state.run_id))

    assert resumed.state is RunState.BLOCKED
    assert "ambiguous" in resumed.blockers[-1]
    assert gateway.purposes == []


def test_resume_never_promotes_a_blocked_task_to_completed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(registry, worker_outputs=[])
    store = RunStore(tmp_path / "artifacts")
    state = RunContract(
        goal="Do not promote blocked work.",
        repository_root=str(root),
        active_branch="autonomy/test",
        starting_head=git(root, "rev-parse", "HEAD"),
        current_head=git(root, "rev-parse", "HEAD"),
        workspace_diff_hash=GitWorkspace(root).snapshot().diff_hash,
        state=RunState.BLOCKED,
    )
    state.tasks = [
        TaskContract(
            run_id=state.run_id,
            plan_task_id="blocked-task",
            role=LogicalRole.IMPLEMENTATION_WORKER,
            task_kind=TaskKind.IMPLEMENTATION,
            title="Blocked task",
            goal="Remain blocked until explicitly revised.",
            state=TaskState.BLOCKED,
        )
    ]
    store.save_model(str(state.run_id), "run_state.json", state)
    controller = RunController(
        repository_root=root,
        store=store,
        registry=registry,
        gateway=gateway,
        workspace=GitWorkspace(root),
    )

    resumed = controller.resume(str(state.run_id))

    assert resumed.state is RunState.BLOCKED
    assert resumed.tasks[0].state is TaskState.BLOCKED
    assert gateway.purposes == []


def test_resume_restores_persisted_policy_counters(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    registry = ModelRegistry(RegistrySettings())
    gateway = FakeGateway(registry, worker_outputs=[])
    store = RunStore(tmp_path / "artifacts")
    state = RunContract(
        goal="Restore bounded counters.",
        repository_root=str(root),
        active_branch="autonomy/test",
        starting_head=git(root, "rev-parse", "HEAD"),
        current_head=git(root, "rev-parse", "HEAD"),
        workspace_diff_hash=GitWorkspace(root).snapshot().diff_hash,
        state=RunState.EXECUTING,
        policy_counters={
            "max_replans": 1,
            "max_cycles": 3,
            "max_repairs_per_task": 2,
            "max_luna_to_terra_escalations": 1,
            "max_terra_to_sol_escalations": 1,
            "max_independent_critiques": 1,
            "max_identical_retries": 1,
            "replan_count": 1,
            "cycle_count": 2,
            "repairs_by_task": {"task-id": 2},
            "escalations": {"luna->terra": 1},
            "independent_critiques": 1,
        },
    )
    store.save_model(str(state.run_id), "run_state.json", state)
    controller = RunController(
        repository_root=root,
        store=store,
        registry=registry,
        gateway=gateway,
        workspace=GitWorkspace(root),
    )

    resumed = controller.resume(str(state.run_id))

    assert resumed.state is RunState.COMPLETED
    assert controller.policy.replan_count == 1
    assert controller.policy.cycle_count == 2
    assert controller.policy.repairs_by_task == {"task-id": 2}
    assert controller.policy.escalations == {("luna", "terra"): 1}
    assert controller.policy.independent_critiques == 1
