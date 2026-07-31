# careerOS backend

The FastAPI backend for careerOS manages authenticated candidate profiles, job
analysis, resume generation, application history, and generated documents.

## Local testing

Install backend dependencies in a local virtual environment, then use the
frontend acceptance gate to run all repository checks:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
npx playwright install chromium
npm run acceptance
```

`npm run acceptance` is the documented full regression command. It runs backend
pytest, Ruff, backend compilation, frontend type checking, frontend production
build, and the complete Playwright suite sequentially. It exits nonzero when
any check fails.

See [local testing](docs/local_testing.md) for the backend test coverage and
for separately running the application during local development.

## Status

Under development.
