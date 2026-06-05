# careerOS Frontend

The Vite + React frontend for the careerOS application workflow.

## Local Development

Run the FastAPI backend from the workspace root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Store the PostgreSQL URL in the ignored `backend/.env` file:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@localhost/careeros
```

Run the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:3000`. Swagger is available at
`http://127.0.0.1:8000/docs`.

## Environment

Create `frontend/.env.local` when you need to override the local API:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## URL Pipeline

Paste an existing `candidate_profile_id` and a public job-posting URL into the
Analyze a Job section. The frontend sends the request to
`POST /api/v1/pipeline/url`, displays the stored pipeline result, and downloads
the generated resume through `GET /api/v1/documents/{document_id}/download`.

## Manual Import

Use the `Paste job manually` toggle in the Analyze a Job section when a site
blocks browser extraction or hides job text. Paste the candidate profile ID, job
title, company, optional job URL, and full job description.

The frontend sends the request to `POST /api/v1/pipeline/manual`. It runs the
same backend pipeline as URL import after skipping Playwright extraction:

```text
manual job details -> job analysis -> resume analysis -> resume draft -> document generation -> optional application record
```

Manual import is useful for LinkedIn pages that block Playwright, Indeed posts
with hidden content, Glassdoor login pages, or company career pages that render
unusual markup.
