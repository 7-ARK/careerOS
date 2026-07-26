import {defineConfig, devices} from '@playwright/test';
import {execSync} from 'node:child_process';
import {existsSync, mkdirSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {env} from 'node:process';

/**
 * Deterministic local browser test harness for the careerOS frontend.
 *
 * A single command runs the whole suite (no manual pre-start):
 *   cd frontend && npm run test:e2e
 *
 * Playwright starts both servers automatically:
 *   1. The FastAPI backend at PLAYWRIGHT_BACKEND_URL (default
 *      http://127.0.0.1:8000), backed by a disposable SQLite database inside
 *      the gitignored frontend/test-results/ directory, with paid LLM resume
 *      intelligence disabled via USE_LLM_RESUME_INTELLIGENCE=false. Before any
 *      server starts, this config creates the database schema
 *      (Base.metadata.create_all) with the same interpreter and DATABASE_URL,
 *      so no manual migration step is required.
 *   2. The Vite frontend at PLAYWRIGHT_BASE_URL (default
 *      http://127.0.0.1:3000), with VITE_API_BASE_URL pointed at the test
 *      backend. baseURL matches this fixed port.
 *
 * One-time setup:
 *   1. Create the backend virtualenv and install dependencies:
 *        cd backend && python -m venv .venv
 *        .\.venv\Scripts\Activate.ps1   (or: source .venv/bin/activate)
 *        pip install -r requirements.txt
 *      Playwright auto-detects backend/.venv so `uvicorn` is always found;
 *      it falls back to `python` on PATH when no virtualenv exists.
 *   2. cd frontend && npm install && npx playwright install chromium
 *
 * Environment overrides:
 *   - PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000    (frontend origin + baseURL)
 *   - PLAYWRIGHT_BACKEND_URL=http://127.0.0.1:8000 (disposable-state backend)
 *   - PLAYWRIGHT_HEADLESS=true|false               (default: true)
 *   - PLAYWRIGHT_WORKERS=N                         (default: 4)
 */
const baseUrl = (env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000').replace(/\/$/, '');
const backendUrl = (env.PLAYWRIGHT_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const backendPort = new URL(backendUrl).port || '8000';
const headless = env.PLAYWRIGHT_HEADLESS !== 'false';
const workers = env.PLAYWRIGHT_WORKERS ? parseInt(env.PLAYWRIGHT_WORKERS, 10) : 4;

// Disposable local test state: a throwaway SQLite database inside the
// gitignored test-results directory. Delete the file to reset test state.
const artifactDir = resolve(process.cwd(), 'test-results');
mkdirSync(artifactDir, {recursive: true});
const e2eDatabasePath = resolve(artifactDir, 'careeros-e2e.db').split(sep).join('/');
const e2eDatabaseUrl = `sqlite+pysqlite:///${e2eDatabasePath}`;

// Resolve a Python interpreter that has the backend dependencies installed.
// Prefer the backend virtualenv (backend/.venv) so `uvicorn` is always found;
// fall back to `python` on PATH for environments that install globally.
const backendDir = resolve(process.cwd(), '..', 'backend');
const venvPython = process.platform === 'win32'
  ? resolve(backendDir, '.venv', 'Scripts', 'python.exe')
  : resolve(backendDir, '.venv', 'bin', 'python');
const pythonCommand = existsSync(venvPython) ? `"${venvPython}"` : 'python';

// Deterministic startup: create the disposable database schema before any
// webServer launches. Previously uvicorn started against an empty SQLite
// file, so authenticated journeys failed with
// `sqlite3.OperationalError: no such table: users`. `create_all` is
// idempotent, so reruns against an existing database file stay safe, and the
// same interpreter + DATABASE_URL used for uvicorn are used here.
execSync(
  `${pythonCommand} -c "import app.models; from app.db.base import Base; from app.db.session import create_database_engine; from os import environ; Base.metadata.create_all(create_database_engine(environ['DATABASE_URL']))"`,
  {
    cwd: backendDir,
    env: {...process.env, DATABASE_URL: e2eDatabaseUrl},
    stdio: 'inherit',
  },
);

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  fullyParallel: true,
  forbidOnly: !!env.CI,
  retries: env.CI ? 2 : 0,
  workers,
  reporter: [['list'], ['html', {outputFolder: 'playwright-report'}]],
  use: {
    baseURL: baseUrl,
    // retain-on-failure captures evidence with any retry count, including the
    // local default of zero retries (on-first-retry would record nothing).
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless,
    actionTimeout: 15000,
    navigationTimeout: 15000,
  },
  projects: [
    {
      name: 'chromium',
      use: {...devices['Desktop Chrome']},
    },
  ],
  webServer: [
    {
      command: `${pythonCommand} -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: backendDir,
      url: `${backendUrl}/docs`,
      reuseExistingServer: !env.CI,
      timeout: 120 * 1000,
      env: {
        DATABASE_URL: e2eDatabaseUrl,
        USE_LLM_RESUME_INTELLIGENCE: 'false',
      },
    },
    {
      command: 'npm run dev',
      url: baseUrl,
      reuseExistingServer: true,
      timeout: 120 * 1000,
      env: {
        // Keep the dev server stable during agent edits.
        DISABLE_HMR: 'true',
        VITE_API_BASE_URL: backendUrl,
      },
    },
  ],
});
