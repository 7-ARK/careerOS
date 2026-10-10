# Ahmed Raza Seed Profile

## Purpose

`backend/scripts/seed_ahmed_candidate.py` creates a development candidate
profile for Ahmed Raza. It replaces the fictional Amina Rahman seed for private
local testing when you want the generated resume to use Ahmed's own candidate
knowledge base.

The original fake seed remains available as `python -m scripts.seed_candidate`.

## What The Script Creates

The seed creates a fresh candidate profile with:

- Public LinkedIn/GitHub links and an environment-configurable email/phone.
- Bachelor of Artificial Intelligence education at Bahria University Islamabad.
- Ignite Learning tutoring/business/operations experience from 2018 to current.
- Early-career AI engineering, AI automation, backend, cloud ML, MLOps, and
  workflow automation skills.
- Four technical projects:
  - careerOS
  - Legal Document OCR and Extraction System
  - AI Workflow Automation System
  - IBM Dev Day / Ops Incident First Response Agent
- Four certifications, including Google Cloud ML, Advanced ML on Google Cloud,
  Duke DevOps/DataOps/MLOps, and MLOps platforms.
- Career goals for AI automation, AI engineering, ML internships, Python
  backend, GenAI internships, MLOps internships, and workflow roles.
- ATS-focused preferences that avoid unsupported senior-level claims.

## Run It

From the `backend` directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.seed_ahmed_candidate
```

`DATABASE_URL` is loaded from the ignored `backend/.env` file. Real contact
values must also remain in that ignored file:

```dotenv
CAREEROS_DEVELOPER_EMAIL=your-private-email
CAREEROS_DEVELOPER_PHONE=your-private-phone
```

Without those variables, the script uses a non-deliverable example email and
no phone number.

Example output:

```text
careerOS Ahmed Raza candidate created
candidate_profile_id=0d3f9d7a-2b29-41a2-9843-c5ce24df01d0
candidate_name=Ahmed Raza
skills=24 projects=4 certifications=4
```

Copy the printed `candidate_profile_id` into the frontend Analyze a Job form.

## Why Use This Instead Of The Fake Seed

The fake Amina profile is useful for generic development testing, but it does
not represent Ahmed's real background. This seed lets the URL and manual import
pipelines generate resumes from Ahmed's actual contact details, education,
certifications, projects, skills, and career goals.

## Real Vs Project-Based Data

Profile data:

- Name, location, LinkedIn, and GitHub. Email and phone are private environment overrides.
- Bahria University Islamabad education.
- Ignite Learning online tutoring/business experience.
- Listed certifications and verification URLs where provided.

Project-based technical evidence:

- careerOS.
- Legal document OCR and extraction.
- AI workflow automation.
- IBM Dev Day / Ops incident first response agent.

Truthfulness boundary:

- Ahmed should not be presented as a senior engineer.
- Tutoring/business experience should not be described as software engineering
  employment.
- Technical experience should be represented through projects, certifications,
  and early-career engineering work.
