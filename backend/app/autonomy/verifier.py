"""Controller-owned, allow-listed verification commands."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.autonomy.redaction import redact_text

MAX_VERIFICATION_EXCERPT = 8_000


@dataclass(frozen=True, slots=True)
class VerificationCommand:
    """One command the CEO may select by stable identifier."""

    identifier: str
    working_directory: str
    command: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    """Sanitized result of one controller-owned command."""

    identifier: str
    command: tuple[str, ...]
    working_directory: str
    return_code: int
    passed: bool
    timed_out: bool
    duration_seconds: float
    output_artifact: str
    output_excerpt: str = ""


class ProcessRunner(Protocol):
    """Injectable subprocess boundary."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command without a shell."""


class SubprocessRunner:
    """Default no-shell process runner."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        """Run an allow-listed command and capture text output."""
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )


def default_verification_catalog() -> dict[str, VerificationCommand]:
    """Return the repository's safe verification command catalog."""
    return {
        "backend-pytest": VerificationCommand(
            identifier="backend-pytest",
            working_directory="backend",
            command=(".venv/Scripts/python.exe", "-m", "pytest", "-q"),
            timeout_seconds=300,
        ),
        "backend-ruff": VerificationCommand(
            identifier="backend-ruff",
            working_directory="backend",
            command=(".venv/Scripts/python.exe", "-m", "ruff", "check", "."),
            timeout_seconds=120,
        ),
        "backend-compile": VerificationCommand(
            identifier="backend-compile",
            working_directory="backend",
            command=(".venv/Scripts/python.exe", "-m", "compileall", "app", "tests", "scripts"),
            timeout_seconds=120,
        ),
        "frontend-lint": VerificationCommand(
            identifier="frontend-lint",
            working_directory="frontend",
            command=("npm.cmd", "run", "lint"),
            timeout_seconds=180,
        ),
        "frontend-build": VerificationCommand(
            identifier="frontend-build",
            working_directory="frontend",
            command=("npm.cmd", "run", "build"),
            timeout_seconds=180,
        ),
        "frontend-smoke": VerificationCommand(
            identifier="frontend-smoke",
            working_directory="frontend",
            command=("npx.cmd", "playwright", "test", "tests/smoke.spec.ts"),
            timeout_seconds=240,
        ),
        "frontend-auth-e2e": VerificationCommand(
            identifier="frontend-auth-e2e",
            working_directory="frontend",
            command=("npx.cmd", "playwright", "test", "tests/auth.spec.ts", "--workers=1"),
            timeout_seconds=360,
        ),
    }


class VerificationRunner:
    """Execute only commands declared in the trusted catalog."""

    def __init__(
        self,
        repository_root: Path,
        artifact_directory: Path,
        *,
        catalog: dict[str, VerificationCommand] | None = None,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.artifact_directory = artifact_directory.resolve()
        self.artifact_directory.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog or default_verification_catalog()
        self.process_runner = process_runner or SubprocessRunner()

    def run(self, identifiers: list[str]) -> list[VerificationEvidence]:
        """Run selected checks sequentially and preserve their output."""
        unknown = sorted(set(identifiers).difference(self.catalog))
        if unknown:
            raise ValueError(f"unknown verification identifiers: {', '.join(unknown)}")

        results: list[VerificationEvidence] = []
        for identifier in identifiers:
            spec = self.catalog[identifier]
            started = time.monotonic()
            timed_out = False
            output = ""
            return_code = 124
            try:
                completed = self.process_runner.run(
                    spec.command,
                    cwd=(self.repository_root / spec.working_directory).resolve(),
                    timeout_seconds=spec.timeout_seconds,
                )
                return_code = completed.returncode
                output = f"STDOUT\n{completed.stdout}\nSTDERR\n{completed.stderr}"
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
                output = f"TIMEOUT\nSTDOUT\n{stdout}\nSTDERR\n{stderr}"
            output = redact_text(output)
            duration = time.monotonic() - started
            artifact = self.artifact_directory / f"verification-{identifier}.log"
            artifact.write_text(output, encoding="utf-8", newline="\n")
            results.append(
                VerificationEvidence(
                    identifier=identifier,
                    command=spec.command,
                    working_directory=spec.working_directory,
                    return_code=return_code,
                    passed=return_code == 0 and not timed_out,
                    timed_out=timed_out,
                    duration_seconds=round(duration, 3),
                    output_artifact=str(artifact),
                    output_excerpt=output[-MAX_VERIFICATION_EXCERPT:],
                )
            )
            if not results[-1].passed:
                break
        return results
