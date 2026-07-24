# CareerOS Bounded Autonomy

## Purpose

`app.autonomy` is a repository-local development controller. It accepts a bounded
repository goal, asks a configured CEO model for a typed task graph, delegates scoped
work, validates proposed edits, runs controller-owned checks, and creates commits only
after evidence-based authorization.

It is not part of the customer-facing CareerOS API and it does not automate job
applications, communication, deployment, publishing, or production data changes.

## Authority Model

Models can plan, propose edits, inspect supplied source context, review evidence, and
explain blockers.

Only the controller can:

- apply validated file operations;
- run allow-listed commands;
- change task or run state;
- decide that deterministic verification passed;
- stage explicit files;
- create a Git commit;
- push the active non-main branch.

Reviewer and critic results are advisory evidence. They cannot complete a task.

## Model Registry

All autonomous model routing lives in `app/autonomy/registry.py`.

| Logical role | Primary | Bounded fallback |
| --- | --- | --- |
| CEO | GPT-5.6 Sol | GPT-5.6 Terra |
| Planner | GPT-5.6 Sol | GPT-5.6 Terra |
| Implementation worker | GPT-5.6 Luna | GPT-5.6 Terra |
| Research worker | GPT-5.6 Luna | Kimi K3 |
| Test worker | GPT-5.6 Luna | None by default |
| Reviewer | GPT-5.6 Terra | GPT-5.6 Sol |
| Independent critic | Kimi K3 | Terra is a registry fallback, but live Kimi review skips when Kimi is unavailable |
| Summarizer | GPT-5.6 Luna | None by default |

OpenAI models use the Responses API. Kimi K3 uses Moonshot's official
OpenAI-compatible Chat Completions endpoint at `https://api.moonshot.ai/v1`.

The old `OPENAI_MODEL` setting remains the optional resume-intelligence model and an
explicit compatibility fallback for low-cost autonomy roles. It is never selected
silently.

## Environment

Configure credentials only in `backend/.env`:

```dotenv
OPENAI_API_KEY=
KIMI_API_KEY=
```

Optional routing overrides are listed in `backend/.env.example`. The controller never
places credential values in prompts, manifests, errors, or reports.

## Execution Contract

A persisted run records:

- goal, repository root, branch, starting/current HEAD, and diff hash;
- CEO plan and dependency-ordered task queue;
- assigned logical role and actual model;
- task status, attempts, repairs, evidence, files, and tests;
- provider call IDs, prompt hashes, usage, duration, and fallback decisions;
- controller commits, blockers, and final state.

Task states:

```text
pending -> ready -> running -> validation_required
        -> repair_required -> completed
        -> blocked | skipped | terminal_failed
```

Run states:

```text
planning -> executing -> validating -> repairing -> committing -> completed
        -> blocked | terminal_failed
```

State is atomically persisted after meaningful transitions. A completed validated model
call is cached by provider, model, purpose, prompt, schema, reasoning, and tool policy.
Completed tasks are never rerun. An interrupted provider call or file-application
checkpoint is treated as ambiguous and blocks instead of being replayed.

## Limits

- one initial CEO plan;
- no more than ten tasks;
- one major replan allowance;
- three plan/execute/validate cycles;
- two implementation repairs per task;
- one Luna-to-Terra escalation;
- one Terra-to-Sol escalation;
- one Kimi critique per run;
- one identical retry only for a transient provider error;
- no retries for authentication, access, invalid model, or invalid request failures.

There is no recursive agent spawning or unbounded background loop.

## Safety

The controller refuses:

- `main`, `master`, or detached HEAD;
- unapproved dirty paths;
- absolute or parent-traversal paths;
- `.env`, credential, key, token, password, and secret-bearing paths;
- model-supplied shell commands;
- edits outside a task's scope;
- worker-created commits or branch changes;
- unrelated staged files;
- an implementation task with no relevant diff;
- commit authorization when deterministic verification failed.

Existing dirty files can be adopted only when every path is named explicitly and
`--adopt-existing` is supplied.

## CLI

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.autonomy --help
```

Run:

```powershell
.\.venv\Scripts\python.exe -m app.autonomy run `
  --goal "Complete one bounded repository task" `
  --continuation-file artifacts\autonomous_live_validation_<timestamp>\continuation_map.md `
  --max-tasks 1 `
  --scope frontend\tests
```

Resume:

```powershell
.\.venv\Scripts\python.exe -m app.autonomy resume <run-id>
```

Inspect:

```powershell
.\.venv\Scripts\python.exe -m app.autonomy status <run-id>
```

Probe:

```powershell
.\.venv\Scripts\python.exe -m app.autonomy probe
```

Provider probes and live runs make paid API calls. Deterministic tests must pass before
using them.

## Evidence

Each run writes an ignored directory under `backend/artifacts/autonomy/<run-id>/` with:

- continuation context;
- model registry and availability;
- CEO plan and task graph;
- state transitions;
- provider call metadata and validated call cache;
- worker, reviewer, critic, and CEO decision artifacts;
- command logs and test report;
- commit report;
- final machine manifest;
- human diagnostic report.

Runtime artifacts are never staged automatically.

## Human Gates

Human approval remains required for:

- merging to `main`;
- deployment or publishing;
- real communications or job applications;
- production data or account changes;
- irreversible external actions;
- spending beyond configured provider limits.
