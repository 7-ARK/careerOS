# Local Pipeline Testing

## Purpose

The development seed creates one fictional early-career AI automation and
backend candidate. Use its `candidate_profile_id` to exercise the complete
local workflow:

```text
Job URL
-> Playwright extraction
-> Job analysis
-> Resume analysis
-> Resume draft
-> PDF generation
-> Application record
```

The script uses the Candidate Knowledge Base service, so the seeded profile is
validated and persisted through the same application layer as future onboarding.

## Start PostgreSQL

Create an empty PostgreSQL database and add its SQLAlchemy URL to `backend/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@localhost/careeros
```

The backend loads this ignored local file automatically. The seed script creates
missing tables for local development.

## Seed The Candidate

From the `backend` directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.seed_candidate
```

The command prints a value such as:

```text
careerOS development candidate created
candidate_profile_id=8ae7b653-77a7-4dc4-a196-ced44c471087
candidate_name=Amina Rahman
skills=17 projects=4
```

Copy the UUID after `candidate_profile_id=`. Each run creates a fresh candidate
so that experiments remain isolated.

## Run The Backend

From the `backend` directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Swagger is available at
`http://127.0.0.1:8000/docs`.

## Run The Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:3000`.

## Test A Public Job URL

1. Open `http://localhost:3000`.
2. Select `Start building`.
3. Paste the seeded `candidate_profile_id`.
4. Paste a public job-posting URL.
5. Select `Analyze job`.
6. Review the match score, generated document ID, and application record ID.
7. Select `Download resume`.

## Expected Limitations

- LinkedIn, Indeed, Glassdoor, and company sites may block automated browsing,
  require authentication, render content differently, or expose too little
  visible detail.
- Extraction warnings are expected for incomplete pages. Use the visible
  manual-import link when URL extraction cannot produce a pipeline-ready job.
- The deterministic analyzer does not call OpenAI and intentionally avoids
  inventing candidate evidence.
- The seed contains fictional development data only. Do not use it as a real
  candidate profile.
