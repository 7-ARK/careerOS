# Local Testing

## Full local acceptance gate

The repository's complete local regression command is run from `frontend`:

```powershell
cd frontend
npm run acceptance
```

It uses sequential `&&` commands and exits nonzero as soon as any stage fails.
The gate runs backend pytest, `ruff check .`, backend compilation, frontend
TypeScript checking, the frontend production build, and the full Playwright
suite.

Before the first run, install the local backend and frontend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
npx playwright install chromium
```

On macOS or Linux, activate the virtual environment with
`source .venv/bin/activate`.

## Browser-test runtime

The Playwright stage starts its own local FastAPI and Vite servers. It uses a
throwaway SQLite database at `frontend/test-results/careeros-e2e.db`, with LLM
resume intelligence disabled. The default configuration uses four workers.

The test frontend is fixed at `http://127.0.0.1:3000`; the disposable backend
is fixed at `http://127.0.0.1:8000`. The harness fails if either owned server
port cannot be used, preventing it from silently testing a separately started
server. No local environment file, production database, or external browser
service is used by this browser-test runtime.

Use these commands only for focused browser debugging:

```powershell
cd frontend
npm run test:e2e:auth
npm run test:e2e:smoke
npm run test:e2e:ui
```

## Verified coverage

The browser suite verifies registration, login, logout, and restored sessions;
private candidate-profile creation and editing; validation-value retention and
empty states; manual job analysis, human approval, and PDF resume downloads;
private resource isolation between two users; URL extraction review and manual
fallback; and resume history ordering with historical PDF download.

The URL tests use loopback fixture markup and mocked extraction responses. They
verify the local application flow and fallback behavior, not live job-site
availability or third-party site layouts.

Backend API tests additionally verify registration, duplicate-user handling,
login, the current-user endpoint, required authentication for private
candidate routes, and sanitized owner-scoped rejection for foreign candidate,
application, pipeline, and document identifiers. They verify that rejected
foreign requests do not disclose or mutate owner fixture data.

## Run the application locally

For manual development, configure a local database connection using your own
ignored local environment configuration, then start FastAPI:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

The local backend is available at `http://127.0.0.1:8000`, and its OpenAPI UI
is available at `http://127.0.0.1:8000/docs`. Start Vite separately with
`cd frontend` followed by `npm run dev`.

Manual exploration can cover additional product behavior, but it is not a
substitute for the acceptance gate and is not represented as automated
coverage here.
