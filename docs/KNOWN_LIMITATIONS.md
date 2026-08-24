# Known Limitations

- The guaranteed path uses deterministic rule extraction and feature-hash embeddings. These are reproducible and inspectable, but less semantically capable than a production embedding model.
- The local vector index is rebuilt per retrieval from PostgreSQL source rows and is not designed for large multi-tenant corpora.
- Job URL extraction is optional and depends on public page structure; manual job text is the supported demonstration path, and URL extraction is disabled in shared preview mode.
- Candidate facts are candidate-entered and marked verified within this personal workspace; careerOS does not independently verify employers, credentials, dates, or project outcomes.
- PDF/DOCX resume import uses conservative local heuristics. It requires field-by-field review and does not infer unsupported dates, employers, certifications, ratings, or years of experience.
- Shared preview mode disables resume import, profile editing, and application-tracker mutation so public visitors cannot alter the synthetic fixture.
- The resume editor is review/approve focused. It does not yet support fine-grained inline editing of each generated bullet.
- Generated documents use local filesystem storage. Production deployment needs private object storage, retention policy, malware scanning for any future uploads, and signed downloads.
- PDF export is visually tested but is not claimed to be PDF/UA certified.
- Authentication is local email/password JWT. Password recovery, email verification, OAuth, MFA, rate limiting, and administrative controls are outside this portfolio sprint.
- The Alembic chain represents the current schema. Existing local databases created with `create_all` require deliberate inspection before stamping or upgrading.
- Request/stage logs are structured but are not shipped to a hosted observability backend.
- Docker Compose is a deployment-ready local baseline, not a high-availability cloud architecture.
- No automatic applications, bulk scraping, employer contact, email automation, interview chatbot, or autonomous agent actions are implemented.
- Portfolio GIF/screenshots require manual capture after final visual review.
- No real customers, production traffic, hiring outcomes, or independent candidate-verification results are claimed.
