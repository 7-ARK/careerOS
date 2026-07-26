# careerOS Frontend

The Vite + React frontend for the careerOS application workflow.

## Local Development

Run the FastAPI backend from the workspace root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Store the PostgreSQL URL in the ignored `backend/.env` file:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@localhost/careeros
```

Run the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:3000`. Swagger is available at
`http://127.0.0.1:8000/docs`.

## Environment

Create `frontend/.env.local` when you need to override the local API:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Browser tests

The frontend includes a Playwright harness for local end-to-end tests. Tests
run against Chromium only and do not use cloud browser infrastructure.

A single command runs the whole suite. Playwright starts both servers itself,
so no manual pre-start is required:

- the FastAPI backend at the fixed port `http://127.0.0.1:8000`, backed by a
  disposable local SQLite database at `frontend/test-results/careeros-e2e.db`
  with `USE_LLM_RESUME_INTELLIGENCE=false` (paid LLM resume intelligence
  disabled);
- the Vite frontend at the fixed port `http://127.0.0.1:3000`, with
  `VITE_API_BASE_URL` pointed at the test backend. The Playwright `baseURL`
  matches this port.

Both web servers are pinned to their fixed ports, so a run never silently
attaches to a foreign server: the frontend dev server uses Vite's
`--strictPort`, and the backend is started by a launcher that verifies the
backend port is free before doing anything else. If port 8000 or 3000 is
already in use, the run fails fast instead of testing against the wrong
backend or frontend.

No real database, `.env` file, or cloud service is used during the run.

### Launcher-sequenced startup

Importing `playwright.config.ts` performs no database or filesystem side
effects; it only computes settings. There is no global setup module. All
disposable-state setup is sequenced inside the backend webServer launcher,
`tests/backend-launcher.ts`, which Playwright starts exactly once per test
run (as the backend `webServer` command) before any test worker connects:

1. The launcher fails fast when the fixed backend port is already occupied.
2. It resets only the disposable, gitignored SQLite database file
   (`frontend/test-results/careeros-e2e.db`).
3. It initializes the database schema (`Base.metadata.create_all`) with the
   existing backend SQLAlchemy entry points, using the same interpreter and
   `DATABASE_URL` that the backend will use.
4. Only after schema initialization succeeds does it start uvicorn, and it
   forwards SIGTERM/SIGINT to uvicorn and exits nonzero on any failure.

Because the launcher runs once per run rather than once per worker, all four
default workers share the single initialized database. No manual migration
step is required.

The backend directory and Python interpreter resolution live in one shared
helper, `tests/backend-runtime.ts`, imported by both `playwright.config.ts`
and the launcher, so the resolution logic is never duplicated. That module is
also the single side-effect-free source of truth for the disposable database
path and URL.

### One-time setup

Install the frontend dependencies and the Chromium binary:

```powershell
cd frontend
npm install
npx playwright install chromium
```

Create the backend virtualenv and install its dependencies so Playwright can
launch uvicorn:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

Playwright auto-detects the interpreter: it prefers `backend/.venv`
(`Scripts/python.exe` on Windows, `bin/python` otherwise) and falls back to
`python` on PATH when no virtualenv exists. If you skip the virtualenv, make
sure `python` resolves to an environment where the backend requirements are
installed.

### Run the full suite

```powershell
cd frontend
npm run test:e2e
```

Run with the Playwright UI for debugging:

```powershell
npm run test:e2e:ui
```

### Smoke run

The smoke test (`tests/smoke.spec.ts`) only opens the auth screen and does not
talk to the backend, so it runs safely in parallel across the default four
workers:

```powershell
npm run test:e2e:smoke
```

### Authenticated run

The authenticated journeys (`tests/auth.spec.ts`) register and log in against
the disposable backend that Playwright starts automatically:

```powershell
npm run test:e2e:auth
```

### Disposable test state

Each run uses the throwaway SQLite database
`frontend/test-results/careeros-e2e.db`. The backend launcher recreates the
database schema automatically before starting uvicorn, so no manual migration
step is required. Delete that file to reset the test state completely. Each
test also gets a unique email address via the `isolatedUser` fixture so
parallel workers do not collide. Login state is stored in `localStorage` by
the app and survives page reloads; the harness exercises this in
`tests/auth.spec.ts`.

### Failure artifacts

Traces, screenshots, and videos are retained automatically on failure and
written to `frontend/test-results/`. The HTML report is written to
`frontend/playwright-report/`. Both directories are generated outputs and are
ignored by Git (see `.gitignore`). Open the report with:

```powershell
npx playwright show-report
```

### Environment overrides

```dotenv
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000
PLAYWRIGHT_BACKEND_URL=http://127.0.0.1:8000
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_WORKERS=1
```

## URL Pipeline

Paste an existing `candidate_profile_id` and a public job-posting URL into the
Analyze a Job section. The frontend sends the request to
`POST /api/v1/pipeline/url`, displays the stored pipeline result, and downloads
the generated resume through `GET /api/v1/documents/{document_id}/download`.

## Manual Import

Use the `Paste job manually` toggle in the Analyze a Job section when a site
blocks browser extraction or hides job text. Paste the candidate profile ID, job
title, company, optional job URL, and full job description.

The frontend sends the request to `POST /api/v1/pipeline/manual`. It runs the
same backend pipeline as URL import after skipping Playwright extraction:

```text
manual job details -> job analysis -> resume analysis -> resume draft -> document generation -> optional application record
```

Manual import is useful for LinkedIn pages that block Playwright, Indeed posts
with hidden content, Glassdoor login pages, or company career pages that render
unusual markup.
