# CareerOS workflow and scope

This note matches the workflow in the current code. An earlier sprint plan listed gaps for retrieval, coverage scoring, human approval, Alembic, CI, and the analysis screen. Those items are implemented. They are not repeated here as open work.

## Workflow

The supported path is:

1. Candidate profile.
2. Manual job description. URL extraction can fill the same form, and manual text remains the reliable input.
3. Validated requirements.
4. Candidate evidence retrieval.
5. Requirement by requirement match analysis.
6. Grounded resume draft.
7. Explicit human approval.
8. DOCX and PDF export.
9. Saved application record.

Shared preview keeps URL extraction, profile edits, resume import, and tracker edits disabled.

## What is in the repository

The backend is FastAPI with authenticated routes, SQLAlchemy models, and Alembic migrations. It extracts typed requirements, retrieves candidate owned evidence, and calculates the Evidence Coverage Score in code. Hybrid ranking is 0.7 lexical and 0.3 vector. The default store is the local index rebuilt from PostgreSQL rows. `RAG_VECTOR_STORE=pgvector` stores embeddings in `evidence_embeddings` and still scores them in Python. `RAG_EMBEDDING_PROVIDER=deterministic` is the default and the CI path. `RAG_EMBEDDING_PROVIDER=openai` calls `text-embedding-3-small` and fails if `OPENAI_API_KEY` is missing.

Grounding checks the draft before export. Approval is a separate request. The application tracker stores lifecycle states that include saved, applied, interviewing, offer, and rejected.

The frontend is a React and TypeScript workspace. It shows the evidence map, coverage score, citations, approval gate, downloads, and application status. Playwright covers that flow against a disposable SQLite database.

GitHub Actions runs the backend checks, the frontend type check and build, and Playwright. Docker Compose, the root README, `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`, and `docs/KNOWN_LIMITATIONS.md` are in the tree. The frozen 24 case retrieval benchmark is checked in under `backend/evals/results/`.

## Still outside this repository

These items from the original plan are still true:

1. No automatic or bulk applications.
2. No required browser automation, bulk scraping, or dependence on live job boards. URL extraction is optional.
3. No OAuth, payments, email automation, interview bots, or a job marketplace.
4. No multi agent orchestration and no autonomous application decisions.
5. No separate vector database. Embeddings stay in process or in PostgreSQL.
6. No Kubernetes setup, model fine tuning, or mobile app.
7. Generated resume text does not become verified candidate evidence unless the candidate saves it on the profile.

Other current limits are listed in `docs/KNOWN_LIMITATIONS.md`. They include lexical status labels, local file storage for generated documents, email and password authentication, and the lack of inline bullet editing.
