import {defineConfig, devices} from '@playwright/test';
import {env} from 'node:process';

import {backendDirectory, e2eDatabaseUrl, resolvePythonCommand} from './tests/backend-runtime';

/**
 * Deterministic local browser test harness for the careerOS frontend.
 *
 * A single command runs the whole suite (no manual pre-start):
 *   cd frontend && npm run test:e2e
 *
 * Importing this config has NO database or filesystem side effects; it only
 * computes settings. All disposable-state setup is sequenced inside the
 * backend webServer launcher (tests/backend-launcher.ts), which Playwright
 * starts exactly once per test run before any test worker connects:
 *   1. The launcher fails fast when the fixed backend port is already
 *      occupied, so a run never silently attaches to a foreign server.
 *   2. It resets only the disposable, gitignored SQLite database file.
 *   3. It applies the backend Alembic migrations using the same interpreter
 *      and DATABASE_URL that uvicorn will use.
 *   4. It starts uvicorn only after schema initialization succeeds, with
 *      paid LLM resume intelligence disabled via
 *      USE_LLM_RESUME_INTELLIGENCE=false.
 *
 * Playwright also starts the Vite frontend at PLAYWRIGHT_BASE_URL (default
 * http://127.0.0.1:3000); same-origin `/api` requests use Vite's loopback
 * proxy to reach the test backend. baseURL matches this fixed port. Both servers are pinned to fixed
 * ports: the frontend uses Vite's --strictPort and the backend launcher
 * verifies the backend port is free before starting uvicorn, so a port
 * collision fails fast instead of silently reusing a foreign server.
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

const backendDir = backendDirectory();

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
      // The launcher sequences port verification, disposable database reset,
      // and schema initialization before starting uvicorn. It owns the
      // backend environment (DATABASE_URL, USE_LLM_RESUME_INTELLIGENCE) so
      // the interpreter and database URL are resolved in exactly one place.
      command: `npx tsx tests/backend-launcher.ts`,
      cwd: resolveFrontendDirectory(),
      url: `${backendUrl}/docs`,
      // Never reuse a foreign server: the harness owns this backend and its
      // disposable database for the duration of the run.
      reuseExistingServer: false,
      timeout: 120 * 1000,
      env: {
        PLAYWRIGHT_BACKEND_URL: backendUrl,
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
        VITE_API_PROXY_TARGET: backendUrl,
      },
    },
  ],
});

/** Absolute path of the frontend directory (this config's working directory). */
function resolveFrontendDirectory(): string {
  return process.cwd();
}

// Re-exported for backward compatibility with any tooling that imported the
// disposable database URL from the config. The single source of truth is
// tests/backend-runtime.ts; this re-export performs no I/O.
export {e2eDatabaseUrl};

// Referenced so the resolved backend directory and interpreter stay anchored
// to the shared helper even though the launcher owns the backend process.
void backendDir;
void resolvePythonCommand;
