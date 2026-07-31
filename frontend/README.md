# careerOS Frontend

The Vite + React frontend for the careerOS application workflow.

## Local development

Start the FastAPI backend in one terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:3000`. By default, it sends API
requests to `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` in an ignored
`frontend/.env.local` file only when a different local API URL is needed.

## Local acceptance gate

Run the complete regression gate from `frontend`:

```powershell
npm run acceptance
```

The command is deliberately sequential, using `&&`, so it stops and exits
nonzero at the first failed check. It runs, in order:

1. backend `pytest`;
2. backend `ruff check .`;
3. backend bytecode compilation for `app`;
4. frontend TypeScript checking;
5. frontend production build; and
6. the complete Playwright suite.

Install the required local tooling first:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
npx playwright install chromium
```

On macOS or Linux, activate the backend virtual environment with
`source .venv/bin/activate` instead. The Playwright harness prefers that
virtual environment's Python interpreter and falls back to `python` on PATH.

## Browser-test harness

`npm run test:e2e` starts both test servers; do not start servers manually for
that command. The harness uses a disposable SQLite database at
`frontend/test-results/careeros-e2e.db`, starts FastAPI at
`http://127.0.0.1:8000`, and starts Vite at `http://127.0.0.1:3000` with its
API base URL directed to that backend. It disables LLM resume intelligence.

The configured default is four Playwright workers. Both server ports are fixed:
the Vite command uses `--strictPort`, and the backend launcher rejects an
occupied backend port. A collision therefore fails instead of reusing another
local server. The database and Playwright artifacts are local generated test
state; the suite does not use a real database, local environment file, or
cloud browser service.

For focused browser debugging:

```powershell
npm run test:e2e:auth
npm run test:e2e:smoke
npm run test:e2e:ui
```

Failure traces, screenshots, and videos are retained in `test-results/`; the
HTML report is written to `playwright-report/`.

## Behavior covered by the browser suite

The complete browser suite verifies these user-visible and local API flows:

- registration, login, logout, and session restoration after reload;
- creating a candidate profile, editing it, preserving the selected profile,
  and retaining entered fields after a validation error;
- distinct empty states for users with no profile and profiles with no resume
  history;
- manual job entry, resume generation, and nonempty PDF downloads;
- private candidate, pipeline, and document access for two separate users,
  including sanitized `not_found` responses for foreign identifiers;
- URL extraction into editable job fields, generating from edited extraction
  results, and manual recovery after an extraction failure without creating an
  application record first; and
- resume-history ordering and downloading an older generated PDF.

The URL scenarios use browser-routed loopback fixture content and mocked
extraction responses. They verify the frontend's extraction and fallback
behavior without contacting external job sites.

## Environment overrides for browser tests

```dotenv
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000
PLAYWRIGHT_BACKEND_URL=http://127.0.0.1:8000
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_WORKERS=1
```

`PLAYWRIGHT_WORKERS` is an explicit debugging override; omit it to retain the
configured default of four workers.
