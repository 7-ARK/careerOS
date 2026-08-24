# Cloudflare Tunnel Preview

This runbook starts a temporary, deterministic recruiter preview. Cloudflare
receives only the Vite URL on `127.0.0.1:3000`. Vite forwards same-origin
`/api` requests to FastAPI on `127.0.0.1:8000`; port 8000 never gets its own
public tunnel.

Preview mode deliberately:

- skips local `.env` loading and disables OpenAI-backed behavior;
- uses a fresh SQLite database under the current user's temporary directory;
- seeds only the fictional Amina Rahman candidate and local demo account;
- keeps login enabled while blocking registration, candidate profile writes, and tracker status changes;
- blocks live analysis, URL extraction, and the legacy auto-export pipeline;
- leaves FastAPI docs, OpenAPI, and health endpoints outside the Vite proxy.

The public URL is temporary and still internet-accessible to anyone who has
it. Stop the tunnel when review is complete.

## 1. Backend

Open PowerShell and run:

```powershell
cd C:\Users\Ahmed\careerOS\backend

$previewDb = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP "careeros-cloudflare-preview.db"))
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
if (-not $previewDb.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Preview database must remain inside TEMP."
}
if (Test-Path -LiteralPath $previewDb) {
  [System.IO.File]::Delete($previewDb)
}

$env:CAREEROS_PREVIEW_MODE = "true"
$env:DATABASE_URL = "sqlite+pysqlite:///$($previewDb.Replace('\', '/'))"
$env:USE_LLM_RESUME_INTELLIGENCE = "false"
$env:RAG_EMBEDDING_PROVIDER = "deterministic"
$env:OPENAI_API_KEY = ""
$env:JWT_SECRET_KEY = [guid]::NewGuid().ToString("N")
$env:CORS_ORIGINS = "http://127.0.0.1:3000"

.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_candidate
.\.venv\Scripts\python.exe -m app.scripts.reset_demo_workspace --email demo@careeros.local --dry-run
.\.venv\Scripts\python.exe -m app.scripts.reset_demo_workspace --email demo@careeros.local --seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The seed command prints the synthetic profile ID. Preview login credentials
are `demo@careeros.local` / `password123`.

The reset dry-run must identify one Amina Rahman profile and report
`synthetic_verified=true`. The seeded reset preserves that account and profile,
backs up the SQLite database, removes only its disposable analysis,
application, document, and unshared job records, then creates one completed,
one awaiting-review, and one rejected fictional example through the real
deterministic service flow. It never runs automatically.

Shared preview mode remains read-only for candidate data and tracker status;
resume import, live providers, URL extraction, uploads, and personal-data entry
stay disabled.

## 2. Frontend

Open a second PowerShell window and run:

```powershell
cd C:\Users\Ahmed\careerOS\frontend
$env:VITE_API_BASE_URL = "/api"
$env:VITE_PREVIEW_MODE = "true"
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8000"
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 3000 --strictPort
```

Vite serves the production build only on `http://127.0.0.1:3000`.

## 3. Tunnel

The downloaded file is currently:

```text
C:\Users\Ahmed\Downloads\cloudflared-windows-amd64.msi
```

Install it once from PowerShell. Windows may show an administrator prompt:

```powershell
Start-Process msiexec.exe -Wait -ArgumentList '/i "C:\Users\Ahmed\Downloads\cloudflared-windows-amd64.msi"'
```

Then open a new PowerShell window and start one quick tunnel:

```powershell
cloudflared.exe tunnel --url http://127.0.0.1:3000
```

Share only the generated `https://*.trycloudflare.com` URL. Never create a
tunnel to port 8000. Press `Ctrl+C` in the tunnel terminal to end public access.

Quick Tunnel URLs are temporary, change between sessions, and are not a permanent portfolio
deployment. Do not put one in the repository README or GitHub description.
