# Continuous Integration

CareerOS uses one GitHub Actions workflow with three independent jobs.

## Backend

The backend job installs Python 3.12 dependencies, runs Ruff, compiles the application, and executes
the full pytest suite. Tests use local deterministic providers and must not require an API key.

```powershell
cd backend
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pytest -q
```

## Frontend

The frontend job installs the locked Node 22 dependency tree, runs the TypeScript no-emit check,
and creates the production Vite build.

```powershell
cd frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run build
```

## Browser acceptance

The browser job installs Chromium and runs the complete Playwright suite. The Playwright backend
launcher verifies ports, applies Alembic migrations to a disposable SQLite database, disables paid
providers, and starts FastAPI only after the schema is ready.

```powershell
cd frontend
npx.cmd playwright install chromium
npx.cmd playwright test
```

Generated reports, traces, videos, downloads, databases, virtual environments, and `node_modules`
are ignored and must not be committed. CI receives no provider credential for the deterministic
test path.

## Migration verification

Before a schema change is merged, use a disposable database with the same `DATABASE_URL` for both
commands:

```powershell
cd backend
$env:DATABASE_URL = "sqlite+pysqlite:///$((Join-Path $env:TEMP 'careeros-migration-check.db').Replace('\', '/'))"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

Delete only the explicitly named disposable file after the check. Existing development databases
must be inspected before stamping or migrating.
