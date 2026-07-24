"""Human- and machine-readable autonomous run reports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_final_manifest(
    directory: Path,
    *,
    state: BaseModel | Mapping[str, Any],
    registry_snapshot: Mapping[str, Any],
    availability: list[Mapping[str, Any]],
) -> Path:
    """Write the canonical machine-readable final manifest."""
    state_payload = state.model_dump(mode="json") if isinstance(state, BaseModel) else dict(state)
    payload = {
        "run": state_payload,
        "model_registry": dict(registry_snapshot),
        "model_availability": [dict(item) for item in availability],
    }
    path = directory / "final_run_manifest.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def write_diagnostic_report(
    directory: Path,
    *,
    title: str,
    summary: str,
    sections: Mapping[str, list[str] | str],
) -> Path:
    """Write a concise Markdown diagnostic report."""
    lines = [f"# {title}", "", summary.strip(), ""]
    for heading, content in sections.items():
        lines.extend([f"## {heading}", ""])
        if isinstance(content, str):
            lines.extend([content.strip(), ""])
        else:
            lines.extend([f"- {item}" for item in content] or ["- None"])
            lines.append("")
    path = directory / "diagnostic_report.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return path
