"""Tests for the local autonomy CLI contract."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.autonomy.cli import build_parser, discover_repository_root, main, read_continuation
from app.autonomy.models import RunContract
from app.autonomy.store import RunStore


def test_parser_requires_explicit_continuation_and_goal() -> None:
    parser = build_parser()

    arguments = parser.parse_args(
        [
            "run",
            "--goal",
            "Complete one bounded task.",
            "--continuation-file",
            "continuation.md",
            "--scope",
            "frontend/tests",
            "--context",
            "backend/tests/support.py",
        ]
    )

    assert arguments.command == "run"
    assert arguments.max_tasks == 10
    assert arguments.scope == ["frontend/tests"]
    assert arguments.context == ["backend/tests/support.py"]


def test_status_prints_safe_summary_without_provider_calls(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    subprocess.run(
        ("git", "init", "-b", "autonomy/test"),
        cwd=repository,
        capture_output=True,
        check=True,
    )
    store = RunStore(repository / "backend" / "artifacts" / "autonomy")
    state = RunContract(
        goal="Inspect status.",
        repository_root=str(repository),
        active_branch="autonomy/test",
        current_head="abc123",
    )
    store.save_model(str(state.run_id), "run_state.json", state)
    dotenv_call: dict[str, object] = {}

    def fake_load_dotenv(path: Path, *, override: bool) -> bool:
        dotenv_call.update({"path": path, "override": override})
        return True

    monkeypatch.setattr("app.autonomy.cli.load_dotenv", fake_load_dotenv)

    exit_code = main(
        [
            "--repository",
            str(repository),
            "status",
            str(state.run_id),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["run_id"] == str(state.run_id)
    assert "provider_calls" not in output
    assert dotenv_call == {
        "path": repository / "backend" / ".env",
        "override": True,
    }


def test_continuation_reader_rejects_environment_files(tmp_path: Path) -> None:
    environment = tmp_path / ".env"
    environment.write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="environment"):
        read_continuation(environment, tmp_path)


def test_repository_discovery_uses_git_not_fixed_paths(tmp_path: Path) -> None:
    repository = tmp_path / "custom-name"
    child = repository / "backend" / "nested"
    child.mkdir(parents=True)
    subprocess.run(
        ("git", "init", "-b", "autonomy/test"),
        cwd=repository,
        capture_output=True,
        check=True,
    )

    assert discover_repository_root(child) == repository.resolve()
