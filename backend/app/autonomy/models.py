"""Typed contracts shared by autonomy orchestration and provider adapters."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]


class ContractModel(BaseModel):
    """Strict base for contracts crossing autonomy boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class LogicalRole(StrEnum):
    """Logical responsibility, independent of a concrete provider model."""

    CEO = "ceo"
    PLANNER = "planner"
    IMPLEMENTATION_WORKER = "implementation_worker"
    RESEARCH_WORKER = "research_worker"
    TEST_WORKER = "test_worker"
    REVIEWER = "reviewer"
    INDEPENDENT_CRITIC = "independent_critic"
    SUMMARIZER = "summarizer"

    # Compatibility aliases for the first repository-local prototype.
    WORKER = "implementation_worker"
    CRITIC = "independent_critic"


class TaskKind(StrEnum):
    """High-level kind of controller-owned work."""

    ANALYSIS = "analysis"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"


class TaskState(StrEnum):
    """Persistable task lifecycle states."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    VALIDATION_REQUIRED = "validation_required"
    REPAIR_REQUIRED = "repair_required"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    TERMINAL_FAILED = "terminal_failed"

    # Compatibility aliases.
    SUCCEEDED = "completed"
    FAILED = "terminal_failed"
    CANCELLED = "skipped"


class RunState(StrEnum):
    """Persistable top-level autonomous run states."""

    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REPAIRING = "repairing"
    COMMITTING = "committing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    TERMINAL_FAILED = "terminal_failed"

    # Compatibility aliases.
    PLANNED = "planning"
    RUNNING = "executing"
    SUCCEEDED = "completed"
    FAILED = "terminal_failed"
    CANCELLED = "terminal_failed"


class ProviderCallState(StrEnum):
    """Outcome of a provider invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AvailabilityStatus(StrEnum):
    """Availability result for a provider/model probe."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class ProviderErrorCategory(StrEnum):
    """Safe categories used for retry and routing decisions."""

    AUTHENTICATION = "authentication"
    MODEL_ACCESS = "model_access"
    ENDPOINT_ACCESS = "endpoint_access"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER = "server"
    TRANSIENT = "transient"
    OUTPUT_VALIDATION = "output_validation"
    UNKNOWN = "unknown"


class ProviderEndpoint(StrEnum):
    """Provider API surface used for a model."""

    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"


class CostClass(StrEnum):
    """Relative cost class used for routing decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RetryPolicy(ContractModel):
    """Bounded retry data; identical transient retries never exceed one."""

    max_transient_retries: int = Field(default=1, ge=0, le=1)
    backoff_seconds: float = Field(default=0.0, ge=0, le=60)


class ModelCapabilities(ContractModel):
    """Capabilities that routing and preflight checks may rely on."""

    structured_output: bool = False
    tool_calling: bool = False
    reasoning: bool = False
    vision: bool = False
    multimodal: bool = False


class ModelSpec(ContractModel):
    """A concrete provider model registered for one logical role."""

    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    role: LogicalRole
    base_url: AnyHttpUrl
    api_key_env: str = Field(min_length=1, max_length=100)
    endpoint: ProviderEndpoint = ProviderEndpoint.RESPONSES
    enabled: bool = True
    priority: int = Field(default=1, ge=1, le=100)
    fallback_role: LogicalRole | None = None
    supported_reasoning_efforts: tuple[ReasoningEffort, ...] = ()
    default_reasoning_effort: ReasoningEffort | None = None
    context_window: int | None = Field(default=None, ge=1)
    maximum_output: int | None = Field(default=None, ge=1)
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    cost_class: CostClass = CostClass.MEDIUM
    timeout_seconds: int = Field(default=180, ge=1, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    concurrency_limit: int = Field(default=1, ge=1, le=32)
    availability_status: AvailabilityStatus = AvailabilityStatus.UNKNOWN
    compatibility_fallback: bool = False

    @model_validator(mode="after")
    def validate_reasoning_default(self) -> ModelSpec:
        """Keep the selected default inside the declared supported set."""
        if (
            self.default_reasoning_effort is not None
            and self.default_reasoning_effort not in self.supported_reasoning_efforts
        ):
            raise ValueError("default reasoning effort must be declared as supported")
        return self


class ModelSelection(ContractModel):
    """Resolved model plus explicit fallback provenance."""

    spec: ModelSpec
    fallback_from: str | None = None
    used_compatibility_fallback: bool = False
    warning: str | None = None


class ProviderUsage(ContractModel):
    """Provider-reported token usage, when available."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reported_cost_usd: float | None = Field(default=None, ge=0)


class SanitizedProviderError(ContractModel):
    """Redacted provider failure information safe for persisted diagnostics."""

    category: ProviderErrorCategory
    detail: str = Field(min_length=1, max_length=300)
    retryable: bool = False
    status_code: int | None = Field(default=None, ge=100, le=599)


class ChatMessage(ContractModel):
    """Minimal provider message contract."""

    role: Literal["system", "user", "assistant", "developer"]
    content: str = Field(min_length=1)


class ProviderRequest(ContractModel):
    """Provider call input with explicit retry and output requirements."""

    messages: list[ChatMessage] = Field(min_length=1)
    purpose: str = Field(default="autonomy", min_length=1, max_length=100)
    task_id: UUID | None = None
    run_id: UUID | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    response_format: dict[str, Any] | None = None
    reasoning_effort: ReasoningEffort | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class ProviderCall(ContractModel):
    """Auditable result of one bounded provider execution."""

    call_id: UUID = Field(default_factory=uuid4)
    role: LogicalRole
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    purpose: str = Field(default="autonomy", min_length=1)
    state: ProviderCallState
    attempts: int = Field(ge=1)
    prompt_hash: str | None = Field(default=None, min_length=64, max_length=64)
    response_id: str | None = None
    text: str | None = None
    structured_output: dict[str, Any] | list[Any] | None = None
    usage: ProviderUsage | None = None
    duration_ms: int = Field(ge=0)
    cached: bool = False
    error: SanitizedProviderError | None = None

    @model_validator(mode="after")
    def validate_error_state(self) -> ProviderCall:
        """Keep success and failure fields internally consistent."""
        if self.state is ProviderCallState.SUCCEEDED and self.error is not None:
            raise ValueError("successful provider calls cannot contain an error")
        if self.state is ProviderCallState.FAILED and self.error is None:
            raise ValueError("failed provider calls must contain a sanitized error")
        return self


class AvailabilityProbe(ContractModel):
    """Provider/model availability evidence without credentials or raw output."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: AvailabilityStatus
    authenticated: bool | None = None
    endpoint: ProviderEndpoint | None = None
    endpoint_reachable: bool | None = None
    tool_calling: bool | None = None
    structured_output: bool | None = None
    response_id: str | None = None
    usage: ProviderUsage | None = None
    duration_ms: int = Field(ge=0)
    error: SanitizedProviderError | None = None
    probed_at: datetime | None = None


class TaskPlan(ContractModel):
    """One bounded, dependency-aware CEO task."""

    task_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,39}$")
    task_kind: TaskKind
    title: str = Field(min_length=3, max_length=200)
    goal: str = Field(min_length=5, max_length=2000)
    assigned_role: LogicalRole
    dependencies: list[str] = Field(default_factory=list, max_length=10)
    scope_paths: list[str] = Field(min_length=1, max_length=20)
    context_paths: list[str] = Field(default_factory=list, max_length=20)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=12)
    tests_required: list[str] = Field(default_factory=list, max_length=10)
    commit_message: str | None = Field(default=None, min_length=5, max_length=120)
    risk: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def validate_kind(self) -> TaskPlan:
        """Require commits and verification for implementation tasks."""
        if self.task_kind is TaskKind.IMPLEMENTATION:
            if self.assigned_role not in {
                LogicalRole.IMPLEMENTATION_WORKER,
                LogicalRole.TEST_WORKER,
            }:
                raise ValueError("implementation tasks require a worker role")
            if not self.tests_required:
                raise ValueError("implementation tasks require controller verification")
            if not self.commit_message:
                raise ValueError("implementation tasks require a commit message")
        return self


class RunPlan(ContractModel):
    """One bounded CEO plan."""

    summary: str = Field(min_length=5, max_length=3000)
    tasks: list[TaskPlan] = Field(min_length=1, max_length=10)
    stop_conditions: list[str] = Field(min_length=1, max_length=10)

    @field_validator("tasks")
    @classmethod
    def validate_graph(cls, tasks: list[TaskPlan]) -> list[TaskPlan]:
        """Require unique IDs, known dependencies, and forward execution order."""
        identifiers = [task.task_id for task in tasks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("plan task IDs must be unique")
        seen: set[str] = set()
        for task in tasks:
            unknown = set(task.dependencies).difference(seen)
            if unknown:
                raise ValueError(
                    f"task {task.task_id} has unknown or forward dependencies: "
                    f"{', '.join(sorted(unknown))}"
                )
            seen.add(task.task_id)
        return tasks


class ReviewVerdict(StrEnum):
    """Advisory reviewer outcome."""

    APPROVE = "approve"
    REVISE = "revise"
    BLOCK = "block"


class ReviewerDecision(ContractModel):
    """Evidence-based advisory review; it cannot complete a task."""

    verdict: ReviewVerdict
    summary: str = Field(min_length=1, max_length=3000)
    required_repairs: list[str] = Field(default_factory=list, max_length=12)
    evidence_gaps: list[str] = Field(default_factory=list, max_length=12)


class CriticReview(ContractModel):
    """One independent implementation critique."""

    summary: str = Field(min_length=1, max_length=3000)
    risks: list[str] = Field(default_factory=list, max_length=12)
    confirmations: list[str] = Field(default_factory=list, max_length=12)
    recommended_actions: list[str] = Field(default_factory=list, max_length=12)


class CommitAction(StrEnum):
    """CEO decision after deterministic verification."""

    AUTHORIZE = "authorize"
    REPAIR = "repair"
    BLOCK = "block"


class CommitDecision(ContractModel):
    """CEO authorization consumed by the controller-owned commit path."""

    action: CommitAction
    summary: str = Field(min_length=1, max_length=3000)
    required_repairs: list[str] = Field(default_factory=list, max_length=12)


class AnalysisReport(ContractModel):
    """Structured output for a no-edit analysis task."""

    inspected_paths: list[str] = Field(min_length=1, max_length=30)
    commands_run: list[str] = Field(default_factory=list, max_length=20)
    grounded_findings: list[str] = Field(min_length=1, max_length=30)
    unknown_or_unverified: list[str] = Field(default_factory=list, max_length=20)
    recommended_next_step: str = Field(min_length=1, max_length=2000)


class VerificationRecord(ContractModel):
    """Persisted controller verification evidence."""

    identifier: str
    command: list[str] = Field(default_factory=list)
    working_directory: str = ""
    passed: bool
    return_code: int
    timed_out: bool = False
    duration_seconds: float = Field(ge=0)
    artifact_path: str
    output_excerpt: str = ""


class TaskContract(ContractModel):
    """Controller-owned task state and accumulated evidence."""

    task_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    plan_task_id: str | None = None
    role: LogicalRole
    task_kind: TaskKind
    title: str = Field(min_length=1, max_length=300)
    goal: str = Field(min_length=1)
    state: TaskState = TaskState.PENDING
    attempt: int = Field(default=0, ge=0, le=3)
    repair_attempts: int = Field(default=0, ge=0, le=2)
    assigned_model: str | None = None
    checkpoint_head: str | None = None
    checkpoint_diff_hash: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    scope_paths: list[str] = Field(default_factory=list)
    context_paths: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    tests_required: list[str] = Field(default_factory=list)
    tests_completed: list[VerificationRecord] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    commit_sha: str | None = None
    blockers: list[str] = Field(default_factory=list)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class RunContract(ContractModel):
    """Controller-owned resumable autonomous run state."""

    run_id: UUID = Field(default_factory=uuid4)
    goal: str = Field(default="", max_length=4000)
    repository_root: str = ""
    active_branch: str = ""
    starting_head: str = ""
    current_head: str = ""
    workspace_diff_hash: str = ""
    state: RunState = RunState.PLANNING
    plan: RunPlan | None = None
    tasks: list[TaskContract] = Field(default_factory=list)
    task_queue: list[str] = Field(default_factory=list)
    active_task_id: UUID | None = None
    provider_calls: list[UUID] = Field(default_factory=list)
    commits_created: list[str] = Field(default_factory=list)
    initial_dirty_paths: list[str] = Field(default_factory=list)
    policy_counters: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    final_state: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_active_task(self) -> RunContract:
        """Ensure an active task belongs to this run."""
        task_ids = {task.task_id for task in self.tasks}
        if self.active_task_id is not None and self.active_task_id not in task_ids:
            raise ValueError("active_task_id must reference a task in the run")
        return self


TaskStatus = TaskState
RunStatus = RunState
AvailabilityRecord = AvailabilityProbe


__all__ = [
    "AvailabilityProbe",
    "AvailabilityRecord",
    "AvailabilityStatus",
    "AnalysisReport",
    "ChatMessage",
    "ContractModel",
    "CostClass",
    "CommitAction",
    "CommitDecision",
    "CriticReview",
    "LogicalRole",
    "ModelCapabilities",
    "ModelSelection",
    "ModelSpec",
    "ProviderCall",
    "ProviderCallState",
    "ProviderEndpoint",
    "ProviderErrorCategory",
    "ProviderRequest",
    "ProviderUsage",
    "ReasoningEffort",
    "ReviewVerdict",
    "ReviewerDecision",
    "RetryPolicy",
    "RunContract",
    "RunPlan",
    "RunState",
    "RunStatus",
    "SanitizedProviderError",
    "TaskContract",
    "TaskKind",
    "TaskPlan",
    "TaskState",
    "TaskStatus",
    "VerificationRecord",
]
