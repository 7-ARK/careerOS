"""Command-line entry point for bounded CareerOS autonomy runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from app.autonomy.gateway import ModelGateway
from app.autonomy.models import LogicalRole
from app.autonomy.orchestrator import ControllerOptions, RunController
from app.autonomy.registry import ModelRegistry
from app.autonomy.store import RunStore
from app.autonomy.workspace import GitWorkspace


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI contract."""
    parser = argparse.ArgumentParser(
        prog="python -m app.autonomy",
        description="Run bounded, controller-owned autonomous repository work.",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        help="Target Git repository. Defaults to the repository containing the current directory.",
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        help="Ignored runtime artifact root. Defaults to backend/artifacts/autonomy.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Create and execute one bounded run.")
    run.add_argument("--goal", required=True)
    run.add_argument("--continuation-file", type=Path, required=True)
    run.add_argument("--max-tasks", type=int, default=10)
    run.add_argument("--allow-existing", action="append", default=[])
    run.add_argument("--scope", action="append", default=[])
    run.add_argument("--context", action="append", default=[])
    run.add_argument("--adopt-existing", action="store_true")
    run.add_argument("--skip-critic", action="store_true")
    run.add_argument("--push", action="store_true")

    resume = subparsers.add_parser("resume", help="Resume a persisted non-terminal run.")
    resume.add_argument("run_id")
    resume.add_argument("--allow-existing", action="append", default=[])
    resume.add_argument("--scope", action="append", default=[])
    resume.add_argument("--context", action="append", default=[])
    resume.add_argument("--adopt-existing", action="store_true")
    resume.add_argument("--skip-critic", action="store_true")
    resume.add_argument("--push", action="store_true")

    status = subparsers.add_parser("status", help="Print a safe persisted run summary.")
    status.add_argument("run_id")

    probe = subparsers.add_parser(
        "probe",
        help="Probe Sol, Luna, and Kimi K3 once and store sanitized evidence.",
    )
    probe.add_argument("--run-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one CLI command and print only sanitized summaries."""
    arguments = build_parser().parse_args(argv)
    repository = (
        arguments.repository.resolve()
        if arguments.repository
        else discover_repository_root(Path.cwd())
    )
    backend = repository / "backend"
    # Repository-local provider settings must win over stale global shell values.
    load_dotenv(backend / ".env", override=True)
    artifacts_root = (
        arguments.artifacts_root.resolve()
        if arguments.artifacts_root
        else backend / "artifacts" / "autonomy"
    )
    store = RunStore(artifacts_root)
    registry = ModelRegistry.from_environment()

    if arguments.command == "status":
        state = store.read_json(arguments.run_id, "run_state.json")
        print(
            json.dumps(
                {
                    "run_id": state.get("run_id"),
                    "state": state.get("state"),
                    "active_branch": state.get("active_branch"),
                    "current_head": state.get("current_head"),
                    "commits_created": state.get("commits_created", []),
                    "blockers": state.get("blockers", []),
                },
                indent=2,
            )
        )
        return 0

    gateway = ModelGateway(registry, store, os.environ)
    if arguments.command == "probe":
        run_id = arguments.run_id or datetime.now(UTC).strftime("probe-%Y%m%d-%H%M%S")
        probes = [
            gateway.probe_role(run_id=run_id, role=role)
            for role in (
                LogicalRole.CEO,
                LogicalRole.IMPLEMENTATION_WORKER,
                LogicalRole.INDEPENDENT_CRITIC,
            )
        ]
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "probes": [
                        probe.model_dump(mode="json", exclude={"error"})
                        | {"error_category": (probe.error.category.value if probe.error else None)}
                        for probe in probes
                    ],
                },
                indent=2,
            )
        )
        return 0 if all(probe.status.value == "available" for probe in probes) else 2

    controller = RunController(
        repository_root=repository,
        store=store,
        registry=registry,
        gateway=gateway,
        workspace=GitWorkspace(repository),
    )
    options = ControllerOptions(
        max_tasks=getattr(arguments, "max_tasks", 10),
        allowed_existing_dirty_paths=tuple(arguments.allow_existing),
        allowed_scope_paths=tuple(arguments.scope),
        allowed_context_paths=tuple(arguments.context),
        adopt_existing_dirty=arguments.adopt_existing,
        enable_independent_critic=not arguments.skip_critic,
        push_after_completion=arguments.push,
    )
    if arguments.command == "run":
        continuation = read_continuation(arguments.continuation_file, repository)
        result = controller.start(
            goal=arguments.goal,
            continuation_context=continuation,
            options=options,
        )
    else:
        result = controller.resume(arguments.run_id, options=options)
    print(
        json.dumps(
            {
                "run_id": str(result.run_id),
                "state": result.state.value,
                "branch": result.active_branch,
                "head": result.current_head,
                "commits": result.commits_created,
                "blockers": result.blockers,
                "artifact_directory": str(store.run_directory(str(result.run_id))),
            },
            indent=2,
        )
    )
    return 0 if result.state.value == "completed" else 2


def discover_repository_root(start: Path) -> Path:
    """Discover the current Git root without assuming a fixed path."""
    result = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),
        cwd=start,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("current directory is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def read_continuation(path: Path, repository_root: Path) -> str:
    """Read a non-secret continuation map."""
    resolved = path.resolve()
    lowered = [part.casefold() for part in resolved.parts]
    if any(part == ".env" or part.startswith(".env.") for part in lowered):
        raise ValueError("continuation context cannot be read from an environment file")
    content = resolved.read_text(encoding="utf-8")
    repository_label = repository_root.name
    return f"Repository: {repository_label}\n\n{content}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
