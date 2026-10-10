# careerOS Frontend

The Vite + React frontend for the careerOS application workflow.

## Local development

Start the FastAPI backend in one terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://127.0.0.1:3000`. The default API base is same-origin `/api`. During development, Vite forwards that path to the loopback FastAPI server. Swagger is available at `http://127.0.0.1:8000/docs`.

Create `frontend/.env.local` only when you need an explicit override:

```dotenv
VITE_API_BASE_URL=/api
VITE_PREVIEW_MODE=false
```

## Local acceptance gate

Run the complete regression gate from `frontend`:

```powershell
npm run acceptance
```

The command is sequential and exits nonzero at the first failed check. It runs, in order:

1. backend `pytest`;
2. backend `ruff check .`;
3. backend bytecode compilation for `app`;
4. frontend TypeScript checking;
5. frontend production build;
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

On macOS or Linux, activate the backend virtual environment with `source .venv/bin/activate`. The Playwright harness prefers that virtual environment's Python interpreter and falls back to `python` on PATH.

## Browser tests

`npm run test:e2e` starts both test servers. Do not start them manually for that command. Playwright uses Chromium only.

The harness uses a disposable SQLite database at `frontend/test-results/careeros-e2e.db`. It applies `python -m alembic upgrade head` before uvicorn starts, with `USE_LLM_RESUME_INTELLIGENCE=false`. FastAPI listens at `http://127.0.0.1:8000`. Vite listens at `http://127.0.0.1:3000` and forwards same-origin `/api` requests to that backend. The default is four workers.

Both ports are fixed. Vite uses `--strictPort`, and the backend launcher refuses an occupied port. A collision fails the run instead of attaching to another local server. Importing `playwright.config.ts` does not create the database. Setup runs once inside `tests/backend-launcher.ts`. The suite does not use a real database, a local environment file, or a cloud browser service.

Focused commands:

```powershell
npm run test:e2e:auth
npm run test:e2e:smoke
npm run test:e2e:ui
```

Failure traces, screenshots, and videos stay in `test-results/`. The HTML report is written to `playwright-report/`.

The suite covers registration, login, logout, and session restore; private profile creation and editing; empty states and validation that keeps entered values; manual job analysis, human approval, and nonempty PDF download; owner scoped profile, analysis, pipeline, and document access for two users; URL extraction into editable fields and manual recovery after a typed extraction failure; and resume history order with download of an older PDF.

URL scenarios use loopback fixture content and mocked extraction responses. They do not contact external job sites.

```dotenv
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000
PLAYWRIGHT_BACKEND_URL=http://127.0.0.1:8000
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_WORKERS=1
```

`PLAYWRIGHT_WORKERS` is a debugging override. Omit it to keep four workers.

## Golden Career Analysis

The primary frontend path sends manual job details to `POST /api/v1/career-analyses`. It shows typed requirements, the calculated Evidence Coverage Score, supporting evidence, gaps, and a grounded resume preview. DOCX and PDF generation stay blocked until the user approves the draft at `/api/v1/career-analyses/{run_id}/review`.

`Use job URL` calls `POST /api/v1/pipeline/extract` and copies the result into the same editable fields. A typed failure shows the extraction message and leaves those fields editable. It does not create an application record.

The Applications tab loads `/api/v1/applications/{candidate_id}` and updates lifecycle status through the authenticated status endpoint. Resume history loads `/api/v1/applications/{candidate_id}/history` and can download an older generated file.

`POST /api/v1/pipeline/manual` and `POST /api/v1/pipeline/url` remain available. The recruiter facing screen uses the reviewed analysis endpoint.
