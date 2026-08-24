/**
 * Backend webServer launcher for the Playwright e2e harness.
 *
 * Playwright runs this module as the backend webServer command. It sequences
 * startup deterministically:
 *
 *   1. Fail fast when the fixed backend port is already occupied, so a run
 *      never silently attaches to a foreign server.
 *   2. Reset only the disposable, gitignored SQLite database file, creating
 *      its parent directory first so SQLite can create the database file.
 *   3. Apply the backend Alembic migrations using the same interpreter and
 *      DATABASE_URL that uvicorn will use.
 *   4. Start uvicorn only after schema initialization succeeds, then
 *      propagate server exit and termination signals (SIGTERM/SIGINT)
 *      cleanly, exiting nonzero on any failure.
 *
 * Because the launcher runs once per test run (Playwright starts a single
 * backend webServer shared by all workers), the schema is initialized
 * exactly once and every worker connects to the same initialized database.
 */

import {spawn, spawnSync} from 'node:child_process';
import {createServer} from 'node:net';
import {mkdirSync, rmSync} from 'node:fs';
import {dirname} from 'node:path';

import {
  backendDirectory,
  e2eDatabasePath,
  e2eDatabaseUrl,
  resolvePythonCommand,
} from './backend-runtime';

function fail(message: string): never {
  console.error(`[backend-launcher] ${message}`);
  process.exit(1);
}

function parseBackendPort(): number {
  const backendUrl = (process.env.PLAYWRIGHT_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  let url: URL;
  try {
    url = new URL(backendUrl);
  } catch {
    fail(`PLAYWRIGHT_BACKEND_URL is not a valid URL: ${backendUrl}`);
  }
  const port = Number(url.port || '8000');
  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    fail(`Resolved backend port is invalid: ${url.port}`);
  }
  return port;
}

/**
 * Fail fast when the fixed backend port is already occupied. Attempting to
 * bind the port is the most reliable cross-platform occupancy check: if the
 * bind succeeds the port is free and we immediately release it for uvicorn.
 */
function assertBackendPortFree(port: number): Promise<void> {
  return new Promise((resolvePromise, rejectPromise) => {
    const probe = createServer();
    probe.unref();
    probe.once('error', (error: NodeJS.ErrnoException) => {
      rejectPromise(
        new Error(
          `backend port ${port} is already occupied (${error.code ?? error.message}); ` +
            'stop the process using it before running the e2e suite.',
        ),
      );
    });
    probe.listen(port, '127.0.0.1', () => {
      probe.close(() => resolvePromise());
    });
  });
}

/**
 * Reset only the disposable, gitignored SQLite database file. The parent
 * directory is created first (recursive, no-op when it already exists) so
 * SQLite can create the database file even on a fresh checkout where
 * frontend/test-results/ does not yet exist.
 */
function resetDisposableDatabase(): void {
  const dbPath = e2eDatabasePath();
  mkdirSync(dirname(dbPath), {recursive: true});
  rmSync(dbPath, {force: true});
}

/**
 * Initialize the schema through the production migration path.
 * Throws when initialization fails so uvicorn is never started against an
 * uninitialized database.
 */
function initializeSchema(pythonCommand: string, backendDir: string, databaseUrl: string): void {
  const result = spawnSync(
    pythonCommand,
    ['-m', 'alembic', 'upgrade', 'head'],
    {
      cwd: backendDir,
      env: {...process.env, DATABASE_URL: databaseUrl},
      stdio: 'inherit',
      shell: false,
    },
  );
  if (result.error) {
    throw new Error(`schema initialization failed to start: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`schema initialization exited with status ${result.status ?? 'unknown'}`);
  }
}

async function main(): Promise<void> {
  const port = parseBackendPort();
  const backendDir = backendDirectory();
  const pythonCommand = resolvePythonCommand(backendDir);
  const databaseUrl = e2eDatabaseUrl();

  await assertBackendPortFree(port);
  resetDisposableDatabase();
  initializeSchema(pythonCommand, backendDir, databaseUrl);

  // Schema initialization succeeded; only now start uvicorn.
  const server = spawn(
    pythonCommand,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        USE_LLM_RESUME_INTELLIGENCE: 'false',
        RAG_EMBEDDING_PROVIDER: 'deterministic',
        OPENAI_API_KEY: '',
      },
      stdio: 'inherit',
      shell: false,
    },
  );

  server.once('error', (error) => {
    fail(`failed to start uvicorn: ${error.message}`);
  });

  // Propagate termination signals to uvicorn so Playwright can stop the
  // backend cleanly at the end of the run.
  const forwardSignal = (signal: NodeJS.Signals) => {
    if (!server.killed) {
      server.kill(signal);
    }
  };
  process.on('SIGTERM', () => forwardSignal('SIGTERM'));
  process.on('SIGINT', () => forwardSignal('SIGINT'));

  // Mirror the server exit: nonzero (or signal termination) surfaces as a
  // launcher failure so the run never continues against a dead backend.
  server.once('exit', (code, signal) => {
    if (signal) {
      process.exit(1);
    }
    process.exit(code ?? 1);
  });
}

main().catch((error: unknown) => {
  fail(error instanceof Error ? error.message : String(error));
});
