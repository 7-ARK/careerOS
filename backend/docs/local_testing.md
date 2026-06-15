# Local MVP Testing

## Prerequisites

Create `backend/.env` with a local PostgreSQL connection and a private JWT secret:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@localhost/careeros
JWT_SECRET_KEY=replace-with-a-long-random-local-secret
USE_LLM_RESUME_INTELLIGENCE=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

The OpenAI quality layer is optional. When it is disabled, missing a key, or unavailable,
careerOS uses the deterministic resume-quality implementation.

For a database created before local authentication was added, run from `backend`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.add_user_auth
```

## Optional Demo Account

Seed a complete local candidate profile:

```powershell
cd C:\Users\Ahmed\careerOS\backend
.\.venv\Scripts\Activate.ps1
python -m scripts.seed_candidate
```

The seed creates or reuses this local-only account:

```text
Email: demo@careeros.local
Password: password123
```

Do not use these credentials outside local development.

## Start The Backend

```powershell
cd C:\Users\Ahmed\careerOS\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Backend: `http://127.0.0.1:8000`

Swagger: `http://127.0.0.1:8000/docs`

## Start The Frontend

In another terminal:

```powershell
cd C:\Users\Ahmed\careerOS\frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

## Register Or Login

1. Open the frontend.
2. Register with a name, email, and password of at least eight characters, or log in with
   the demo account.
3. Refresh the page once to confirm the session is restored.
4. Select **Logout** and confirm the login screen returns.

## Create And Select A Profile

1. Select **Create profile**.
2. Enter a full name and any relevant contact details, summary, skills, certifications,
   projects, experience, and education.
3. Select **Save profile** and confirm the success message appears.
4. Confirm the new profile is selected in the candidate dropdown.
5. Edit one field and save again to verify updates.

Candidate profiles are private. A different account must not see the profile in its dropdown
or access its profile ID through the API.

## Test Job URL Extraction

1. Select a candidate profile.
2. Choose **Use URL**.
3. Paste one public LinkedIn, Indeed, Glassdoor, Greenhouse, or Lever job URL.
4. Select **Extract Job**.
5. Confirm job title, company, location, and description populate the editable job form.
6. Review or edit the fields before selecting **Analyze Job**.

Some sites may display login walls, CAPTCHAs, or changed page layouts. careerOS should show a
clear extraction warning and keep manual entry available instead of crashing.

## Test Manual Fallback

1. Select **Paste job manually**.
2. Enter job title, company, and the complete job description.
3. Optionally enter location, source platform, job URL, and company email.
4. Select the desired PDF, DOCX, or Markdown output.
5. Select **Analyze Job**.

The job description must not be empty, and a candidate profile must be selected.

## Generate And Download A Resume

1. Wait for the completed match and resume review result.
2. Confirm the selected projects and skill matches belong to the selected candidate.
3. Select **Download resume**.
4. Open the downloaded file and verify it uses the selected candidate and current job.
5. For PDF output, confirm the file opens normally and internal truthfulness warnings are not
   printed inside the resume.

Repeat once for PDF, DOCX, and Markdown when validating all exporters.

## Expected MVP Limitations

- Access tokens expire after 24 hours and there are no refresh tokens.
- There is no password reset, email verification, OAuth, roles, or payments.
- Job-site login walls, CAPTCHAs, and layout changes can prevent URL extraction.
- Extraction is synchronous and intended for one user-provided URL at a time.
- The optional OpenAI quality layer falls back to deterministic processing when unavailable.
