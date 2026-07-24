"""Tests for autonomous run storage and bounded repository context."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.autonomy.context import ContextResolver
from app.autonomy.store import RunStore


class ExampleState(BaseModel):
    status: str
    count: int


def test_run_store_round_trips_state_and_appends_events(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "artifacts")

    store.save_model("run-1", "state", ExampleState(status="running", count=1))
    store.append_event("run-1", {"event": "task_started", "task_id": "task-1"})

    restored = store.load_model("run-1", "state", ExampleState)
    event_lines = (tmp_path / "artifacts" / "run-1" / "state_transitions.jsonl").read_text(
        encoding="utf-8"
    )

    assert restored == ExampleState(status="running", count=1)
    event = json.loads(event_lines)
    assert event["event"] == "task_started"
    assert event["task_id"] == "task-1"
    assert event["timestamp"]


@pytest.mark.parametrize("run_id", ["../escape", "Run 1", "a/b", ""])
def test_run_store_rejects_unsafe_run_ids(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError):
        RunStore(tmp_path).run_directory(run_id)


def test_context_resolver_reads_only_scoped_source_files(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    (repository / "app").mkdir(parents=True)
    (repository / "app" / "main.py").write_text("print('safe')\n", encoding="utf-8")
    (repository / "app" / "ignored.png").write_bytes(b"\x89PNG")
    (repository / ".env").write_text("SECRET=value\n", encoding="utf-8")

    packet = ContextResolver(repository).build(["app"])

    assert [item.path for item in packet.files] == ["app/main.py"]
    assert "safe" in packet.render()
    assert "SECRET" not in packet.render()


def test_context_resolver_rejects_environment_and_parent_paths(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    resolver = ContextResolver(repository)

    with pytest.raises(ValueError, match="environment"):
        resolver.build([".env"])
    with pytest.raises(ValueError, match="unsafe"):
        resolver.build(["../outside.txt"])


def test_context_resolver_enforces_file_and_total_limits(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "a.py").write_text("a" * 20, encoding="utf-8")
    (repository / "b.py").write_text("b" * 20, encoding="utf-8")

    packet = ContextResolver(
        repository,
        max_files=1,
        max_file_bytes=10,
        max_total_bytes=10,
    ).build(["a.py", "b.py"])

    assert len(packet.files) == 1
    assert packet.files[0].truncated is True
    assert packet.omitted_paths == ("b.py",)
