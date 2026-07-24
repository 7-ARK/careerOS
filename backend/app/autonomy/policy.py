"""Deterministic safety and bounded-execution policy for autonomous work."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Final


class PolicyViolation(ValueError):
    """Raised when a proposed autonomous action violates a repository policy."""


class FailureClass(StrEnum):
    """Failure categories used by the bounded retry policy."""

    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    ACCESS_DENIED = "access_denied"
    INVALID_MODEL = "invalid_model"
    INVALID_REQUEST = "invalid_request"
    PERMANENT = "permanent"


TRANSIENT_FAILURES: Final[frozenset[FailureClass]] = frozenset(
    {FailureClass.TRANSIENT, FailureClass.TIMEOUT}
)
PROTECTED_BRANCHES: Final[frozenset[str]] = frozenset({"main", "master"})
DEFAULT_PROHIBITED_NAMES: Final[tuple[str, ...]] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.*",
    "*credentials*",
    "*secret*",
    "*password*",
    "*token*",
)


def normalize_relative_path(path: str) -> str:
    """Normalize a repository path and reject absolute or traversal paths."""

    if not isinstance(path, str) or not path.strip():
        raise PolicyViolation("repository path must be a non-empty string")
    candidate = path.replace("\\", "/").strip()
    windows = PureWindowsPath(candidate)
    posix = PurePosixPath(candidate)
    if windows.is_absolute() or posix.is_absolute() or windows.drive:
        raise PolicyViolation(f"absolute repository path is not allowed: {path!r}")
    parts = tuple(part for part in posix.parts if part not in ("", "."))
    if ".." in parts:
        raise PolicyViolation(f"repository traversal path is not allowed: {path!r}")
    if not parts:
        raise PolicyViolation("repository path cannot resolve to the repository root")
    return "/".join(parts)


def is_prohibited_path(path: str, patterns: tuple[str, ...] = DEFAULT_PROHIBITED_NAMES) -> bool:
    """Return whether a normalized path could expose a secret or credential."""

    normalized = normalize_relative_path(path)
    path_obj = PurePosixPath(normalized)
    for part in path_obj.parts:
        lowered = part.lower()
        if lowered == ".git" or lowered.startswith(".env"):
            return True
        if any(
            path_obj.match(pattern) or PurePosixPath(part).match(pattern) for pattern in patterns
        ):
            return True
    return False


def validate_branch(branch: str, protected: frozenset[str] = PROTECTED_BRANCHES) -> str:
    """Require a named, non-protected branch for autonomous repository work."""

    if not branch or branch == "HEAD":
        raise PolicyViolation("autonomous work requires a named branch")
    if branch in protected:
        raise PolicyViolation(f"autonomous work is not allowed on {branch!r}")
    return branch


@dataclass(frozen=True, slots=True)
class TaskScope:
    """Allowed repository paths for one bounded worker task."""

    allowed_paths: tuple[str, ...] = ()
    prohibited_patterns: tuple[str, ...] = DEFAULT_PROHIBITED_NAMES
    max_changed_files: int | None = None

    def __post_init__(self) -> None:
        normalized = tuple(normalize_relative_path(path) for path in self.allowed_paths)
        object.__setattr__(self, "allowed_paths", normalized)

    def allows(self, path: str) -> bool:
        """Return whether a path is inside the task's declared scope."""

        normalized = normalize_relative_path(path)
        if is_prohibited_path(normalized, self.prohibited_patterns):
            return False
        return any(
            normalized == allowed or normalized.startswith(f"{allowed}/")
            for allowed in self.allowed_paths
        )

    def validate(self, paths: list[str] | tuple[str, ...] | set[str]) -> tuple[str, ...]:
        """Validate and normalize a set of changed paths against this scope."""

        normalized = tuple(dict.fromkeys(normalize_relative_path(path) for path in paths))
        if self.max_changed_files is not None and len(normalized) > self.max_changed_files:
            raise PolicyViolation("task changed more files than its declared bound")
        invalid = tuple(path for path in normalized if not self.allows(path))
        if invalid:
            raise PolicyViolation(f"changed paths exceed task scope: {', '.join(invalid)}")
        return normalized


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Explain whether a bounded retry is permitted."""

    allowed: bool
    reason: str


@dataclass(slots=True)
class BoundedExecutionPolicy:
    """Counters and limits for one autonomous run.

    The policy is intentionally stateful so a controller can persist the counters
    after each transition without allowing a hidden retry loop.
    """

    max_replans: int = 1
    max_cycles: int = 3
    max_repairs_per_task: int = 2
    max_luna_to_terra_escalations: int = 1
    max_terra_to_sol_escalations: int = 1
    max_independent_critiques: int = 1
    max_identical_retries: int = 1
    replan_count: int = 0
    cycle_count: int = 0
    repairs_by_task: dict[str, int] = field(default_factory=dict)
    escalations: dict[tuple[str, str], int] = field(default_factory=dict)
    independent_critiques: int = 0

    def allow_replan(self) -> RetryDecision:
        return self._decision(self.replan_count, self.max_replans, "major replan")

    def record_replan(self) -> None:
        self._consume(self.allow_replan(), "replan_count")
        self.replan_count += 1

    def allow_cycle(self) -> RetryDecision:
        return self._decision(self.cycle_count, self.max_cycles, "plan-execute-validate cycle")

    def record_cycle(self) -> None:
        self._consume(self.allow_cycle(), "cycle_count")
        self.cycle_count += 1

    def allow_repair(self, task_id: str) -> RetryDecision:
        count = self.repairs_by_task.get(task_id, 0)
        return self._decision(count, self.max_repairs_per_task, f"repair for {task_id}")

    def record_repair(self, task_id: str) -> None:
        self._consume(self.allow_repair(task_id), f"repair for {task_id}")
        self.repairs_by_task[task_id] = self.repairs_by_task.get(task_id, 0) + 1

    def allow_escalation(self, from_role: str, to_role: str) -> RetryDecision:
        limit = {
            ("luna", "terra"): self.max_luna_to_terra_escalations,
            ("terra", "sol"): self.max_terra_to_sol_escalations,
        }.get((from_role.lower(), to_role.lower()), 0)
        count = self.escalations.get((from_role.lower(), to_role.lower()), 0)
        if limit == 0:
            return RetryDecision(False, "escalation path is not permitted")
        return self._decision(count, limit, f"{from_role}->{to_role} escalation")

    def record_escalation(self, from_role: str, to_role: str) -> None:
        decision = self.allow_escalation(from_role, to_role)
        self._consume(decision, f"{from_role}->{to_role} escalation")
        key = (from_role.lower(), to_role.lower())
        self.escalations[key] = self.escalations.get(key, 0) + 1

    def allow_independent_critic(self) -> RetryDecision:
        return self._decision(
            self.independent_critiques,
            self.max_independent_critiques,
            "independent critic review",
        )

    def record_independent_critic(self) -> None:
        self._consume(self.allow_independent_critic(), "independent critic review")
        self.independent_critiques += 1

    def retry_decision(
        self,
        failure: FailureClass | str,
        identical_retries: int,
    ) -> RetryDecision:
        """Allow one identical retry only for transient failures."""

        try:
            category = FailureClass(failure)
        except ValueError:
            return RetryDecision(False, "unknown failures are not retryable")
        if category not in TRANSIENT_FAILURES:
            return RetryDecision(False, f"{category.value} failures are not retryable")
        return self._decision(
            identical_retries, self.max_identical_retries, "identical transient retry"
        )

    @staticmethod
    def _decision(current: int, limit: int, label: str) -> RetryDecision:
        if current < limit:
            return RetryDecision(True, f"{label} remains within its bound")
        return RetryDecision(False, f"{label} limit reached")

    @staticmethod
    def _consume(decision: RetryDecision, label: str) -> None:
        if not decision.allowed:
            raise PolicyViolation(f"cannot consume {label}: {decision.reason}")


__all__ = [
    "BoundedExecutionPolicy",
    "DEFAULT_PROHIBITED_NAMES",
    "FailureClass",
    "PolicyViolation",
    "RetryDecision",
    "TaskScope",
    "is_prohibited_path",
    "normalize_relative_path",
    "validate_branch",
]
