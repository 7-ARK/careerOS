import {execSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';

import {initializeE2eState} from './e2e-state';

/**
 * Playwright global setup: runs exactly once per test run, in the runner
 * process, before any webServer or worker starts.
 *
 * This is the single place that touches the disposable test database. It
 * resets the run-scoped state (tests/e2e-state.ts) and creates the database
 * schema with the same interpreter and DATABASE_URL that the backend
 * webServer will use, so all four default workers share one initialized
 * database and importing playwright.config.ts never performs I/O.
 */
export default function globalSetup(): void {
  const state = initializeE2eState();

  const backendDir = resolve(process.cwd(), '..', 'backend');
  const venvPython = process.platform === 'win32'
    ? resolve(backendDir, '.venv', 'Scripts', 'python.exe')
    : resolve(backendDir, '.venv', 'bin', 'python');
  const pythonCommand = existsSync(venvPython) ? `"${venvPython}"` : 'python';

  // `create_all` runs against the fresh disposable database file. Because
  // global setup runs once per run (not once per worker), the schema is
  // initialized exactly once and every worker connects to the same file.
  execSync(
    `${pythonCommand} -c "import app.models; from app.db.base import Base; from app.db.session import create_database_engine; from os import environ; Base.metadata.create_all(create_database_engine(environ['DATABASE_URL']))"`,
    {
      cwd: backendDir,
      env: {...process.env, DATABASE_URL: state.databaseUrl},
      stdio: 'inherit',
    },
  );
}
