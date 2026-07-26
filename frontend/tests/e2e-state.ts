import {mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {resolve, sep} from 'node:path';

/**
 * Run-scoped disposable state for the Playwright e2e harness.
 *
 * The disposable SQLite database lives inside the gitignored
 * frontend/test-results/ directory. tests/global-setup.ts initializes the
 * schema exactly once per run (in the Playwright runner process, before any
 * worker starts) and records the resulting state here so every one of the
 * default four workers shares the single initialized database instead of
 * creating its own.
 */

export interface E2eState {
  /** Absolute path of the disposable SQLite database file for this run. */
  databasePath: string;
  /** SQLAlchemy URL pointing at the disposable database. */
  databaseUrl: string;
  /** ISO timestamp of when global setup initialized the database. */
  initializedAt: string;
}

const artifactDir = resolve(process.cwd(), 'test-results');
const stateFilePath = resolve(artifactDir, 'e2e-state.json');

/** Absolute path of the disposable SQLite database file for this run. */
export function e2eDatabasePath(): string {
  return resolve(artifactDir, 'careeros-e2e.db');
}

/** SQLAlchemy URL for the disposable database (forward slashes for SQLite). */
export function e2eDatabaseUrl(): string {
  const normalized = e2eDatabasePath().split(sep).join('/');
  return `sqlite+pysqlite:///${normalized}`;
}

/**
 * Initialize the run-scoped state exactly once: remove any stale database
 * from a previous run, create the artifact directory, and persist the state
 * descriptor for workers to read. Returns the state so global setup can pass
 * it to the schema-initialization step.
 */
export function initializeE2eState(): E2eState {
  mkdirSync(artifactDir, {recursive: true});
  // Start each run from a clean slate so leftover rows from a previous run
  // cannot leak into this one. Deleting the file is the documented reset.
  rmSync(e2eDatabasePath(), {force: true});
  const state: E2eState = {
    databasePath: e2eDatabasePath(),
    databaseUrl: e2eDatabaseUrl(),
    initializedAt: new Date().toISOString(),
  };
  writeFileSync(stateFilePath, JSON.stringify(state, null, 2));
  return state;
}

/**
 * Read the run-scoped state written by global setup. Workers call this to
 * locate the single shared database; it throws if global setup has not run.
 */
export function readE2eState(): E2eState {
  const raw = readFileSync(stateFilePath, 'utf-8');
  return JSON.parse(raw) as E2eState;
}
