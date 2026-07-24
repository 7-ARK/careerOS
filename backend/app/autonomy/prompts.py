"""Role-specific prompts for the bounded autonomous controller."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

CONTROLLER_RULES = """
The controller owns state transitions, verification, Git staging, commits, pushes, and stopping.
You must not claim that commands ran unless their controller evidence is provided.
Never request or reveal secrets, .env files, credentials, cookies, or authorization headers.
Never deploy, publish, send communications, submit applications, alter production data, merge,
rebase, reset, clean, switch branches, or push.
Return only the requested structured result.
""".strip()


def ceo_plan_prompt(
    *,
    goal: str,
    continuation_context: str,
    repository_summary: Mapping[str, Any],
    max_tasks: int,
) -> tuple[str, str]:
    """Build the bounded CEO planning prompt."""
    instructions = f"""
You are the CEO/overseer for a bounded repository implementation run.
{CONTROLLER_RULES}
Create one plan with at most {max_tasks} tasks. Every task must have a concrete scope, explicit
dependencies, measurable acceptance criteria, and controller-owned verification IDs.
Use implementation workers for edits, research workers for read-only evidence, and test workers
only for focused test work. Do not delegate routine work to the CEO.
Do not invent files. Prefer the smallest plan that can complete the stated goal.
""".strip()
    payload = {
        "goal": goal,
        "repository": dict(repository_summary),
        "continuation_context": continuation_context,
    }
    return instructions, json.dumps(payload, indent=2, sort_keys=True)


def worker_prompt(
    *,
    task: Mapping[str, Any],
    context_packet: str,
    previous_failure: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Build one scoped worker implementation prompt."""
    instructions = f"""
You are a focused coding worker operating under a controller-owned task.
{CONTROLLER_RULES}
Inspect only the supplied context. Do not explore other directories and do not redesign the
system. Propose only file writes or exact text replacements inside task scope. For existing files,
include their supplied sha256 as expected_sha256. Report every file read and every proposed edit.
Do not say tests passed; the controller runs tests after applying changes.
If the task cannot be completed from this scope, return a blocker instead of guessing.
""".strip()
    payload: dict[str, Any] = {
        "task": dict(task),
        "repository_context": context_packet,
    }
    if previous_failure:
        payload["previous_verification_failure"] = dict(previous_failure)
    return instructions, json.dumps(payload, indent=2, sort_keys=True)


def reviewer_prompt(
    *,
    task: Mapping[str, Any],
    diff_summary: str,
    verification: list[Mapping[str, Any]],
    worker_evidence: Mapping[str, Any],
) -> tuple[str, str]:
    """Build an evidence-only reviewer prompt."""
    instructions = f"""
You are an independent reviewer. You are advisory and cannot complete tasks or create commits.
{CONTROLLER_RULES}
Judge whether the scoped implementation meets every acceptance criterion using only the supplied
diff and controller-owned verification evidence. Reject unsupported claims, missing tests,
unrelated edits, scope expansion, secret exposure, or mocked output presented as live.
""".strip()
    payload = {
        "task": dict(task),
        "diff_summary": diff_summary,
        "verification": [dict(item) for item in verification],
        "worker_evidence": dict(worker_evidence),
    }
    return instructions, json.dumps(payload, indent=2, sort_keys=True)


def critic_prompt(
    *,
    task: Mapping[str, Any],
    diff_summary: str,
    verification: list[Mapping[str, Any]],
) -> tuple[str, str]:
    """Build one independent long-context critic prompt."""
    instructions = f"""
You are an independent long-context implementation critic, not the CEO.
{CONTROLLER_RULES}
Critique the proposed package. Identify at least one concrete risk, weakness, or evidence-backed
confirmation. Do not create a competing plan and do not propose unrelated features.
""".strip()
    payload = {
        "task": dict(task),
        "diff_summary": diff_summary,
        "verification": [dict(item) for item in verification],
    }
    return instructions, json.dumps(payload, indent=2, sort_keys=True)


def commit_authorization_prompt(
    *,
    goal: str,
    task: Mapping[str, Any],
    reviewer: Mapping[str, Any],
    critic: Mapping[str, Any] | None,
    verification: list[Mapping[str, Any]],
    changed_files: list[str],
) -> tuple[str, str]:
    """Build the CEO's evidence-based commit authorization prompt."""
    instructions = f"""
You are the CEO/overseer making a bounded commit authorization decision.
{CONTROLLER_RULES}
Authorize a controller commit only when all acceptance criteria are evidenced, required tests
passed, changed files are within scope, and no reviewer blocker remains. Otherwise return a
specific repair request or a terminal blocker. You do not create the commit yourself.
""".strip()
    payload = {
        "goal": goal,
        "task": dict(task),
        "reviewer": dict(reviewer),
        "critic": dict(critic) if critic else None,
        "verification": [dict(item) for item in verification],
        "changed_files": changed_files,
    }
    return instructions, json.dumps(payload, indent=2, sort_keys=True)
