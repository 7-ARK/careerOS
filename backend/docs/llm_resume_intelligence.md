# LLM Resume Intelligence

## Purpose

The optional OpenAI Resume Intelligence layer improves resume wording, skill grouping, project explanations, and truthfulness review after the deterministic pipeline has already produced evidence-backed analysis.

The deterministic engine remains the source of reliability. OpenAI is an enhancement layer, not a dependency for resume generation.

## Configuration

Add these values to `backend/.env`:

```env
OPENAI_API_KEY=your_key_here
USE_LLM_RESUME_INTELLIGENCE=true
OPENAI_MODEL=gpt-4.1-mini
```

Defaults:

```env
USE_LLM_RESUME_INTELLIGENCE=false
OPENAI_MODEL=gpt-4.1-mini
```

## Fallback Behavior

LLM mode only runs when:

- `USE_LLM_RESUME_INTELLIGENCE=true`
- `OPENAI_API_KEY` exists

If the key is missing, the SDK is unavailable, the OpenAI call fails, or the response fails validation, careerOS falls back to the deterministic Resume Quality Engine. Resume generation must not fail only because the LLM layer failed.

Fallback warnings are returned to the frontend review panel. They are not rendered inside the PDF.

## What OpenAI Is Used For

- Professional summary refinement
- Skill grouping suggestions
- Project selection/exclusion explanations
- Resume strategy notes
- Truthfulness and overclaim review
- Cloud certification wording nuance

## What OpenAI Is Not Used For

- It is not used as the source of truth.
- It is not allowed to invent experience.
- It does not create employers, dates, degrees, certifications, salaries, or links.
- It does not run agents, browser automation, RAG, vector search, or Canva workflows.
- It does not replace deterministic matching.

## Truthfulness Rules

LLM recommendations must be classified as:

- `supported`
- `weakly_supported`
- `unsupported`

Only supported or weakly supported content may affect resume-facing content. Unsupported recommendations are returned as frontend warnings only.

Coursework/certifications must stay distinct from production experience. For example:

- Allowed: `Google Cloud ML coursework`
- Allowed: `Certified in Machine Learning on Google Cloud`
- Allowed: `Exposure to Vertex AI and BigQuery ML`
- Not allowed unless supported: `Deployed production GCP systems`
- Not allowed unless supported: `Managed production Vertex AI pipelines`

## Privacy Notes

The LLM payload contains only structured resume/job facts:

- Candidate profile facts
- Skills
- Projects
- Experience
- Education
- Certifications
- Job analysis fields
- Existing deterministic match/warning output

careerOS does not send environment variables, API keys, database URLs, application logs, or unrelated backend state.

## Testing

LLM tests use fake clients. They do not call OpenAI and do not require an API key.

Run:

```powershell
cd backend
pytest
ruff check .
python -m compileall app tests scripts
```

For frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```
