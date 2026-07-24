"""Tests for the controller-owned verification catalog."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.autonomy.verifier import (
    VerificationCommand,
    VerificationRunner,
)


class FakeProcessRunner:
    def __init__(self, return_codes: list[int]) -> None:
        self.return_codes = return_codes
        self.calls: list[tuple[tuple[str, ...], Path, int]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, cwd, timeout_seconds))
        return_code = self.return_codes[len(self.calls) - 1]
        return subprocess.CompletedProcess(
            args=command,
            returncode=return_code,
            stdout=f"return={return_code}",
            stderr="",
        )


def test_verifier_runs_only_catalog_commands_and_stops_on_failure(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    runner = FakeProcessRunner([0, 1, 0])
    catalog = {
        "first": VerificationCommand("first", "backend", ("python", "-m", "first"), 10),
        "second": VerificationCommand("second", "backend", ("python", "-m", "second"), 10),
        "third": VerificationCommand("third", "backend", ("python", "-m", "third"), 10),
    }
    verifier = VerificationRunner(
        repository,
        tmp_path / "artifacts",
        catalog=catalog,
        process_runner=runner,
    )

    results = verifier.run(["first", "second", "third"])

    assert [result.identifier for result in results] == ["first", "second"]
    assert results[0].passed is True
    assert results[1].passed is False
    assert len(runner.calls) == 2
    assert Path(results[1].output_artifact).exists()


def test_verifier_rejects_model_supplied_unknown_commands(tmp_path: Path) -> None:
    verifier = VerificationRunner(
        tmp_path,
        tmp_path / "artifacts",
        catalog={},
        process_runner=FakeProcessRunner([]),
    )

    with pytest.raises(ValueError, match="unknown verification"):
        verifier.run(["powershell-delete-everything"])


def test_verifier_redacts_failure_output_before_repair_evidence(tmp_path: Path) -> None:
    class SecretOutputRunner(FakeProcessRunner):
        def run(
            self,
            command: tuple[str, ...],
            *,
            cwd: Path,
            timeout_seconds: int,
        ) -> subprocess.CompletedProcess[str]:
            self.calls.append((command, cwd, timeout_seconds))
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="OPENAI_API_KEY=sk-test-secret-value",
                stderr="verification failed",
            )

    verifier = VerificationRunner(
        tmp_path,
        tmp_path / "artifacts",
        catalog={"check": VerificationCommand("check", ".", ("check",), 10)},
        process_runner=SecretOutputRunner([1]),
    )

    result = verifier.run(["check"])[0]

    assert "sk-test-secret-value" not in result.output_excerpt
    assert "[REDACTED]" in result.output_excerpt
    assert "sk-test-secret-value" not in Path(result.output_artifact).read_text(encoding="utf-8")
