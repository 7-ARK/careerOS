"""Validated file operations proposed by autonomous workers."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class FileOperationKind(StrEnum):
    """Supported non-destructive repository edit operations."""

    WRITE = "write"
    REPLACE = "replace"


class FileOperation(BaseModel):
    """One hash-guarded file operation proposed by a worker."""

    kind: FileOperationKind
    path: str = Field(min_length=1, max_length=300)
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    content: str | None = None
    old_text: str | None = None
    new_text: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> FileOperation:
        """Require the fields appropriate for the selected operation."""
        if self.kind == FileOperationKind.WRITE:
            if self.content is None:
                raise ValueError("write operations require content")
            if self.old_text is not None or self.new_text is not None:
                raise ValueError("write operations cannot include replacement fields")
        if self.kind == FileOperationKind.REPLACE:
            if not self.old_text:
                raise ValueError("replace operations require non-empty old_text")
            if self.new_text is None:
                raise ValueError("replace operations require new_text")
            if self.content is not None:
                raise ValueError("replace operations cannot include content")
            if self.expected_sha256 is None:
                raise ValueError("replace operations require expected_sha256")
        return self


class WorkerOutput(BaseModel):
    """Structured evidence returned by a scoped implementation worker."""

    summary: str = Field(min_length=1, max_length=3000)
    files_read: list[str] = Field(default_factory=list, max_length=20)
    operations: list[FileOperation] = Field(default_factory=list, max_length=20)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    blockers: list[str] = Field(default_factory=list, max_length=10)


class AppliedOperation(BaseModel):
    """Controller record of an applied file operation."""

    path: str
    before_sha256: str | None
    after_sha256: str
    kind: FileOperationKind


class FileOperationApplier:
    """Apply only validated operations inside a declared task scope."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()

    def apply(
        self,
        operations: list[FileOperation],
        *,
        allowed_paths: list[str],
    ) -> list[AppliedOperation]:
        """Validate all operations before applying them in order."""
        allowed = tuple(self._resolve_path(value) for value in allowed_paths)
        prepared: list[tuple[FileOperation, Path, str | None, str]] = []
        seen_paths: set[Path] = set()
        for operation in operations:
            path = self._resolve_path(operation.path)
            if path in seen_paths:
                raise ValueError(f"worker proposed multiple operations for {operation.path}")
            seen_paths.add(path)
            if not self._is_allowed(path, allowed):
                raise ValueError(f"worker operation is outside task scope: {operation.path}")
            before = path.read_text(encoding="utf-8") if path.exists() else None
            before_hash = self._sha256_text(before) if before is not None else None
            if operation.expected_sha256 != before_hash:
                if not (operation.expected_sha256 is None and before is None):
                    raise ValueError(f"stale file hash for {operation.path}")
            if operation.kind == FileOperationKind.WRITE:
                assert operation.content is not None
                after = operation.content
            else:
                assert before is not None
                assert operation.old_text is not None
                assert operation.new_text is not None
                occurrences = before.count(operation.old_text)
                if occurrences != 1:
                    raise ValueError(
                        f"replacement target must occur exactly once in {operation.path}; "
                        f"found {occurrences}"
                    )
                after = before.replace(operation.old_text, operation.new_text, 1)
            prepared.append((operation, path, before_hash, after))

        applied: list[AppliedOperation] = []
        for operation, path, before_hash, after in prepared:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(after, encoding="utf-8", newline="\n")
            applied.append(
                AppliedOperation(
                    path=operation.path,
                    before_sha256=before_hash,
                    after_sha256=self._sha256_text(after),
                    kind=operation.kind,
                )
            )
        return applied

    def current_sha256(self, path: str) -> str | None:
        """Return a source file hash for worker stale-write protection."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return None
        return hashlib.sha256(resolved.read_bytes()).hexdigest()

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not value.strip():
            raise ValueError(f"unsafe repository path: {value!r}")
        lowered = [part.casefold() for part in path.parts]
        if any(part == ".env" or part.startswith(".env.") for part in lowered):
            raise ValueError("workers cannot read or edit environment files")
        if any(
            marker in part
            for part in lowered
            for marker in ("credential", "secret", "private_key", "id_rsa")
        ):
            raise ValueError("workers cannot edit secret-bearing paths")
        resolved = (self.repository_root / path).resolve()
        if resolved != self.repository_root and self.repository_root not in resolved.parents:
            raise ValueError(f"repository path escapes root: {value!r}")
        return resolved

    @staticmethod
    def _is_allowed(path: Path, allowed_paths: tuple[Path, ...]) -> bool:
        return any(path == allowed or allowed in path.parents for allowed in allowed_paths)

    @staticmethod
    def _sha256_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
