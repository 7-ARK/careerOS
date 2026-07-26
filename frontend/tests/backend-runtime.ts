import {existsSync} from 'node:fs';
import {resolve, sep} from 'node:path';

/**
 * Shared runtime resolution for the Playwright e2e harness.
 *
 * This module is the single source of truth for:
 *   - the backend directory location;
 *   - the Python interpreter used to run backend commands (schema
 *     initialization and uvicorn);
 *   - the disposable SQLite database path and URL.
 *
 * It is imported by both playwright.config.ts and tests/backend-launcher.ts
 * so interpreter resolution is never duplicated. Every function here is a
 * pure computation: importing this module performs no filesystem or
 * database writes.
 */

/** Absolute path of the backend directory (../backend relative to frontend/). */
export function backendDirectory(): string {
  return resolve(process.cwd(), '..', 'backend');
}

/**
 * Resolve a Python interpreter that has the backend dependencies installed.
 * Prefer the backend virtualenv (backend/.venv) so `uvicorn` is always found;
 * fall back to `python` on PATH for environments that install globally.
 *
 * The returned value is the raw absolute executable path (no surrounding
 * quotes): the launcher spawns it with an argument array and shell: false,
 * so Node resolves the executable directly and quotes would be treated as
 * literal filename characters (spawnSync ENOENT).
 */
export function resolvePythonCommand(backendDirPath: string = backendDirectory()): string {
  const venvPython = process.platform === 'win32'
    ? resolve(backendDirPath, '.venv', 'Scripts', 'python.exe')
    : resolve(backendDirPath, '.venv', 'bin', 'python');
  return existsSync(venvPython) ? venvPython : 'python';
}

/** Absolute path of the disposable SQLite database file for this run. */
export function e2eDatabasePath(): string {
  return resolve(process.cwd(), 'test-results', 'careeros-e2e.db');
}

/** SQLAlchemy URL for the disposable database (forward slashes for SQLite). */
export function e2eDatabaseUrl(): string {
  const normalized = e2eDatabasePath().split(sep).join('/');
  return `sqlite+pysqlite:///${normalized}`;
}
