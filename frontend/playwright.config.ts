import {defineConfig, devices} from '@playwright/test';
import {existsSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {env} from 'node:process';

/**
 * Deterministic local browser test harness for the careerOS frontend.
 *
 * A single command runs the whole suite (no manual pre-start):
 *   cd frontend && npm run test:e2e
 *
 * Importing this config has NO database or filesystem side effects. The
 * disposable SQLite database schema is initialized exactly once per test run
 * by tests/global-setup.ts (see `globalSetup` below), which records the
 * run-scoped database path in tests/e2e-state.ts so all workers share the
 * single initialized database.
 *
 * Playwright starts both servers automatically, each pinned to a fixed port
 * with strictPort so a port collision fails fast instead of silently reusing
 * a foreign server:
 *   1. The FastAPI backend at PLAYWRIGHT_BACKEND_URL (default
 *      http://127.0.0.1:8000), backed by the disposable SQLite database,
 *      with paid LLM resume intelligence disabled via
 *      USE_LLM_RESUME_INTELLIGENCE=false.
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
const frontendPort = new URL(baseUrl).port || '3000';
const headless = env.PLAYWRIGHT_HEADLESS !== 'false';
const workers = env.PLAYWRIGHT_WORKERS ? parseInt(env.PLAYWRIGHT_WORKERS, 10) : 4;

const backendDir = resolve(process.cwd(), '..', 'backend');

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  // Initializes the disposable database exactly once per run, before any
  // worker or webServer starts. See tests/global-setup.ts.
  globalSetup: './tests/global-setup.ts',
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
      command: `${resolvePythonCommand(backendDir)} -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: backendDir,
      url: `${backendUrl}/docs`,
      // Never reuse a foreign server: the harness owns this backend and its
      // disposable database for the duration of the run.
      reuseExistingServer: false,
      timeout: 120 * 1000,
      env: {
        DATABASE_URL: e2eDatabaseUrl(),
        USE_LLM_RESUME_INTELLIGENCE: 'false',
      },
    },
    {
      command: `npm run dev -- --port ${frontendPort} --strictPort`,
      url: baseUrl,
      reuseExistingServer: false,
      timeout: 120 * 1000,
      env: {
        // Keep the dev server stable during agent edits.
        DISABLE_HMR: 'true',
        VITE_API_BASE_URL: backendUrl,
      },
    },
  ],
});

/**
 * Resolve a Python interpreter that has the backend dependencies installed.
 * Prefer the backend virtualenv (backend/.venv) so `uvicorn` is always found;
 * fall back to `python` on PATH for environments that install globally.
 */
function resolvePythonCommand(backendDirPath: string): string {
  const venvPython = process.platform === 'win32'
    ? resolve(backendDirPath, '.venv', 'Scripts', 'python.exe')
    : resolve(backendDirPath, '.venv', 'bin', 'python');
  return existsSync(venvPython) ? `"${venvPython}"` : 'python';
}

/**
 * The disposable local test database URL. This is a pure function of the
 * working directory; it performs no I/O. The file itself is created and its
 * schema initialized once per run by tests/global-setup.ts.
 */
export function e2eDatabaseUrl(): string {
  const artifactDir = resolve(process.cwd(), 'test-results');
  const e2eDatabasePath = resolve(artifactDir, 'careeros-e2e.db').split(sep).join('/');
  return `sqlite+pysqlite:///${e2eDatabasePath}`;
}
