"""Bounded repository context packets for planners and workers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

MAX_CONTEXT_FILES = 12
MAX_FILE_BYTES = 32_000
MAX_TOTAL_BYTES = 160_000

_BINARY_SUFFIXES = {
    ".7z",
    ".avi",
    ".bin",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".webp",
    ".zip",
}


@dataclass(frozen=True, slots=True)
class ContextFile:
    """One repository file included in a bounded model context."""

    path: str
    sha256: str
    content: str
    truncated: bool


@dataclass(frozen=True, slots=True)
class ContextPacket:
    """A deterministic, size-bounded repository context packet."""

    files: tuple[ContextFile, ...]
    omitted_paths: tuple[str, ...]

    def render(self) -> str:
        """Render the packet for a model prompt."""
        sections: list[str] = []
        for item in self.files:
            marker = " (truncated)" if item.truncated else ""
            sections.append(
                f"### {item.path}{marker}\nsha256: {item.sha256}\n```text\n{item.content}\n```"
            )
        if self.omitted_paths:
            sections.append(
                "### Omitted paths\n" + "\n".join(f"- {path}" for path in self.omitted_paths)
            )
        return "\n\n".join(sections)


class ContextResolver:
    """Read only explicitly scoped, safe repository files."""

    def __init__(
        self,
        repository_root: Path,
        *,
        max_files: int = MAX_CONTEXT_FILES,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_total_bytes: int = MAX_TOTAL_BYTES,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

    def build(self, paths: list[str]) -> ContextPacket:
        """Build a deterministic packet from concrete repository-relative paths."""
        candidates: list[Path] = []
        omitted: list[str] = []
        for value in paths:
            resolved = self._resolve_safe_path(value)
            if resolved.is_dir():
                for child in sorted(resolved.rglob("*")):
                    if child.is_file() and self._is_readable_source(child):
                        candidates.append(child)
            elif resolved.is_file() and self._is_readable_source(resolved):
                candidates.append(resolved)
            else:
                omitted.append(value)

        files: list[ContextFile] = []
        total_bytes = 0
        seen: set[Path] = set()
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            relative = resolved.relative_to(self.repository_root).as_posix()
            if len(files) >= self.max_files:
                omitted.append(relative)
                continue
            raw = resolved.read_bytes()
            if total_bytes >= self.max_total_bytes:
                omitted.append(relative)
                continue
            allowed = min(self.max_file_bytes, self.max_total_bytes - total_bytes)
            selected = raw[:allowed]
            try:
                content = selected.decode("utf-8")
            except UnicodeDecodeError:
                omitted.append(relative)
                continue
            files.append(
                ContextFile(
                    path=relative,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    content=content,
                    truncated=len(selected) < len(raw),
                )
            )
            total_bytes += len(selected)
        return ContextPacket(files=tuple(files), omitted_paths=tuple(sorted(set(omitted))))

    def _resolve_safe_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not value.strip():
            raise ValueError(f"unsafe context path: {value!r}")
        if any(
            part.casefold() == ".env" or part.casefold().startswith(".env.") for part in path.parts
        ):
            raise ValueError("environment files cannot be included in model context")
        resolved = (self.repository_root / path).resolve()
        if resolved != self.repository_root and self.repository_root not in resolved.parents:
            raise ValueError(f"context path escapes repository: {value!r}")
        return resolved

    @staticmethod
    def _is_readable_source(path: Path) -> bool:
        if path.suffix.casefold() in _BINARY_SUFFIXES:
            return False
        parts = {part.casefold() for part in path.parts}
        return not parts.intersection(
            {".git", ".venv", "__pycache__", "node_modules", "dist", "artifacts"}
        )
