"""Atomic runtime state and evidence storage for autonomous runs."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


class RunStore:
    """Persist one autonomous run without relying on a database service."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_directory(self, run_id: str) -> Path:
        """Return the validated directory for a run."""
        if not run_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in run_id
        ):
            raise ValueError(
                "run_id must contain only lowercase letters, digits, hyphens, or underscores"
            )
        path = (self.root / run_id).resolve()
        if self.root not in path.parents:
            raise ValueError("run directory escapes the configured artifact root")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_model(self, run_id: str, name: str, model: BaseModel) -> Path:
        """Atomically persist a Pydantic model as JSON."""
        return self.write_json(run_id, name, model.model_dump(mode="json"))

    def load_model(self, run_id: str, name: str, model_type: type[ModelT]) -> ModelT:
        """Load and validate one persisted Pydantic model."""
        payload = self.read_json(run_id, name)
        return model_type.model_validate(payload)

    def write_json(self, run_id: str, name: str, payload: Mapping[str, Any] | list[Any]) -> Path:
        """Atomically write a JSON artifact."""
        path = self._artifact_path(run_id, name, suffix=".json")
        serialized = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
        self._atomic_write(path, serialized)
        return path

    def read_json(self, run_id: str, name: str) -> dict[str, Any]:
        """Read a JSON object artifact."""
        path = self._artifact_path(run_id, name, suffix=".json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{name} must contain a JSON object")
        return payload

    def write_text(self, run_id: str, name: str, content: str) -> Path:
        """Atomically write a UTF-8 text artifact."""
        path = self._artifact_path(run_id, name)
        self._atomic_write(path, content)
        return path

    def append_event(self, run_id: str, event: Mapping[str, Any]) -> Path:
        """Append one timestamped event to the run ledger."""
        path = self._artifact_path(run_id, "state_transitions.jsonl")
        payload = {"timestamp": utc_now(), **dict(event)}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def append_records(
        self,
        run_id: str,
        name: str,
        records: Iterable[Mapping[str, Any]],
    ) -> Path:
        """Append sanitized records to a JSONL artifact."""
        path = self._artifact_path(run_id, name)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(dict(record), sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def exists(self, run_id: str, name: str) -> bool:
        """Return whether a named run artifact exists."""
        return self._artifact_path(run_id, name).exists()

    def _artifact_path(self, run_id: str, name: str, *, suffix: str | None = None) -> Path:
        if not name or Path(name).name != name:
            raise ValueError("artifact names must be plain filenames")
        if suffix and not name.endswith(suffix):
            name = f"{name}{suffix}"
        run_directory = self.run_directory(run_id)
        path = (run_directory / name).resolve()
        if run_directory not in path.parents:
            raise ValueError("artifact path escapes the run directory")
        return path

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
