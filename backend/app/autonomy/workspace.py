"""Dependency-injected Git workspace inspection and controller commit guards."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.autonomy.policy import (
    PolicyViolation,
    TaskScope,
    is_prohibited_path,
    normalize_relative_path,
    validate_branch,
)
from app.autonomy.redaction import redact_command, redact_text


class WorkspaceError(RuntimeError):
    """Raised when a Git workspace cannot satisfy an autonomy safety invariant."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of one injected command invocation."""

    arguments: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class CommandRunner(Protocol):
    """Protocol implemented by subprocess and deterministic test runners."""

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...


class SubprocessCommandRunner:
    """Run commands without a shell and return redacted diagnostics on failure."""

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        command = tuple(str(argument) for argument in arguments)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=dict(env) if env is not None else None,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = (
                error.stdout.decode(errors="replace")
                if isinstance(error.stdout, bytes)
                else error.stdout
            )
            stderr = (
                error.stderr.decode(errors="replace")
                if isinstance(error.stderr, bytes)
                else error.stderr
            )
            return CommandResult(
                arguments=redact_command(command),
                returncode=-1,
                stdout=redact_text(stdout or ""),
                stderr=redact_text(stderr or ""),
                timed_out=True,
            )
        return CommandResult(
            arguments=redact_command(command),
            returncode=completed.returncode,
            stdout=redact_text(completed.stdout),
            stderr=redact_text(completed.stderr),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """Immutable branch, HEAD, status, and diff evidence."""

    branch: str
    head: str
    status: str
    changed_files: tuple[str, ...]
    staged_files: tuple[str, ...]
    diff_hash: str


@dataclass(frozen=True, slots=True)
class CommitResult:
    """Controller-owned commit evidence."""

    commit: str
    branch: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PushResult:
    """Verified active-branch push evidence."""

    branch: str
    commit: str
    remote: str


class GitWorkspace:
    """Perform bounded Git operations against one repository root.

    Worker execution is intentionally absent. Workers may produce a diff, but
    only ``controller_commit`` can stage and commit it.
    """

    def __init__(self, root: str | Path, runner: CommandRunner | None = None) -> None:
        self.root = Path(root).resolve()
        self.runner = runner or SubprocessCommandRunner()
        if not self.root.is_dir():
            raise WorkspaceError(f"workspace root does not exist: {self.root}")

    def snapshot(self) -> WorkspaceSnapshot:
        """Capture branch, HEAD, porcelain status, changed files, and diff hash."""

        branch = self._git_text(("branch", "--show-current")).strip()
        head = self._git_text(("rev-parse", "HEAD")).strip()
        status_result = self._run(("status", "--porcelain=v1", "--untracked-files=all", "-z"))
        status = status_result.stdout
        changed, staged = _parse_status(status)
        diff = self._git_text(("diff", "HEAD", "--binary"))
        digest = hashlib.sha256()
        digest.update(status.encode())
        digest.update(diff.encode())
        for path in changed:
            candidate = self.root / Path(path)
            if path not in staged and candidate.is_file() and not path.lower().startswith(".env"):
                digest.update(path.encode())
                digest.update(candidate.read_bytes())
        return WorkspaceSnapshot(
            branch=branch,
            head=head,
            status=status,
            changed_files=changed,
            staged_files=staged,
            diff_hash=digest.hexdigest(),
        )

    def assert_safe_branch(self, branch: str | None = None) -> str:
        """Reject main/master and detached HEAD before autonomous work."""

        actual = branch if branch is not None else self.snapshot().branch
        try:
            return validate_branch(actual)
        except PolicyViolation as error:
            raise WorkspaceError(str(error)) from error

    def validate_paths(self, paths: Sequence[str], scope: TaskScope) -> tuple[str, ...]:
        """Validate worker paths using the repository-relative task scope."""

        try:
            return scope.validate(list(paths))
        except PolicyViolation as error:
            raise WorkspaceError(str(error)) from error

    def changed_files(self) -> tuple[str, ...]:
        """Return the current repository-relative changed-file set."""

        return self.snapshot().changed_files

    def review_diff(self, paths: Sequence[str], *, max_characters: int = 80_000) -> str:
        """Return a bounded redacted patch, including untracked source files."""
        normalized = tuple(normalize_relative_path(path) for path in paths)
        result = self._run(("diff", "--", *normalized))
        if not result.ok:
            raise WorkspaceError(f"git diff failed: {redact_text(result.stderr).strip()}")
        sections = [result.stdout]
        tracked = set(
            path for path in self._git_text(("ls-files", "--", *normalized)).splitlines() if path
        )
        for path in normalized:
            if path in tracked:
                continue
            candidate = self.root / path
            if candidate.is_file() and not is_prohibited_path(path):
                content = candidate.read_text(encoding="utf-8")
                sections.append(f"\n--- /dev/null\n+++ b/{path}\n{content}")
        return redact_text("\n".join(sections))[:max_characters]

    def verify_post_worker(
        self,
        before: WorkspaceSnapshot,
        *,
        scope: TaskScope,
        expected_branch: str | None = None,
        expected_head: str | None = None,
    ) -> WorkspaceSnapshot:
        """Ensure a worker stayed on branch, made no commit, and stayed in scope."""

        after = self.snapshot()
        if after.branch != (expected_branch or before.branch):
            raise WorkspaceError("worker changed the active branch")
        if after.head != (expected_head or before.head):
            raise WorkspaceError("worker created or moved a commit")
        try:
            scope.validate(after.changed_files)
        except PolicyViolation as error:
            raise WorkspaceError(str(error)) from error
        return after

    def controller_commit(
        self,
        message: str,
        *,
        intended_paths: Sequence[str],
        before: WorkspaceSnapshot | None = None,
        expected_branch: str | None = None,
        expected_head: str | None = None,
        scope: TaskScope | None = None,
        adopt_preexisting_paths: bool = False,
    ) -> CommitResult:
        """Stage explicit paths and create one controller-owned commit.

        The method preserves unrelated baseline-dirty paths. Adopting a baseline
        dirty path requires an explicit flag. It never uses ``git add .`` or
        ``git commit -a``.
        """

        current = self.snapshot()
        self.assert_safe_branch(current.branch)
        if expected_branch is not None and current.branch != expected_branch:
            raise WorkspaceError("controller commit branch does not match the expected branch")
        if expected_head is not None and current.head != expected_head:
            raise WorkspaceError("controller commit HEAD does not match the expected HEAD")
        try:
            normalized = tuple(
                dict.fromkeys(normalize_relative_path(path) for path in intended_paths)
            )
        except PolicyViolation as error:
            raise WorkspaceError(str(error)) from error
        if not normalized:
            raise WorkspaceError("controller commit requires explicit changed paths")
        prohibited = tuple(path for path in normalized if is_prohibited_path(path))
        if prohibited:
            raise WorkspaceError(
                f"controller commit includes prohibited paths: {', '.join(prohibited)}"
            )
        if scope is not None:
            self.validate_paths(normalized, scope)
        baseline_dirty: set[str] = set()
        if before is not None:
            if before.staged_files:
                raise WorkspaceError("refusing commit while pre-existing staged changes exist")
            baseline_dirty = set(before.changed_files)
            adopted = set(normalized).intersection(baseline_dirty)
            if adopted and not adopt_preexisting_paths:
                raise WorkspaceError(
                    "refusing to adopt a path that was already dirty without explicit approval"
                )
        current_dirty = set(current.changed_files)
        intended = set(normalized)
        if not intended.issubset(current_dirty):
            raise WorkspaceError("controller commit includes a path with no current change")
        unrelated_new = current_dirty.difference(baseline_dirty, intended)
        if unrelated_new:
            raise WorkspaceError(
                "refusing commit with unrelated new changes: " + ", ".join(sorted(unrelated_new))
            )
        result = self._run(("add", "--", *normalized))
        if not result.ok:
            raise WorkspaceError(f"git add failed: {redact_text(result.stderr).strip()}")
        staged = self.snapshot().staged_files
        if set(staged) != set(normalized):
            raise WorkspaceError("explicit staging did not produce the declared path set")
        result = self._run(("commit", "-m", message))
        if not result.ok:
            raise WorkspaceError(f"controller commit failed: {redact_text(result.stderr).strip()}")
        after = self.snapshot()
        if after.branch != current.branch or after.head == current.head:
            raise WorkspaceError("controller commit postcondition failed")
        expected_remaining = baseline_dirty.difference(intended)
        if set(after.changed_files) != expected_remaining:
            raise WorkspaceError("controller commit did not preserve the expected baseline diff")
        return CommitResult(commit=after.head, branch=after.branch, changed_files=normalized)

    def controller_push(self, *, remote: str = "origin") -> PushResult:
        """Push only the active non-main branch and verify the remote SHA."""
        snapshot = self.snapshot()
        branch = self.assert_safe_branch(snapshot.branch)
        result = self._run(("push", "-u", remote, branch))
        if not result.ok:
            raise WorkspaceError(f"git push failed: {redact_text(result.stderr).strip()}")
        verification = self.runner.run(
            ("git", "ls-remote", "--heads", remote, branch),
            cwd=self.root,
            timeout=60,
        )
        if not verification.ok:
            raise WorkspaceError("remote branch verification failed")
        fields = verification.stdout.strip().split()
        if len(fields) < 2 or fields[0] != snapshot.head:
            raise WorkspaceError("remote branch does not match the local controller commit")
        return PushResult(branch=branch, commit=snapshot.head, remote=remote)

    def _git_text(self, arguments: Sequence[str]) -> str:
        result = self._run(arguments)
        if not result.ok:
            raise WorkspaceError(
                f"git command failed ({result.returncode}): {redact_text(result.stderr).strip()}"
            )
        return result.stdout

    def _run(self, arguments: Sequence[str]) -> CommandResult:
        result = self.runner.run(("git", *arguments), cwd=self.root)
        if result.timed_out:
            raise WorkspaceError("git command timed out")
        return result


def _parse_status(status: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    records = status.split("\0")
    changed: list[str] = []
    staged: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            continue
        flags = record[:2]
        path = record[3:].replace("\\", "/")
        changed.append(path)
        if flags[0] not in {" ", "?"}:
            staged.append(path)
        if "R" in flags or "C" in flags:
            if index < len(records) and records[index]:
                renamed = records[index].replace("\\", "/")
                changed.append(renamed)
                if flags[0] not in {" ", "?"}:
                    staged.append(renamed)
                index += 1
    return tuple(dict.fromkeys(changed)), tuple(dict.fromkeys(staged))


__all__ = [
    "CommandResult",
    "CommandRunner",
    "CommitResult",
    "GitWorkspace",
    "PushResult",
    "SubprocessCommandRunner",
    "WorkspaceError",
    "WorkspaceSnapshot",
]
