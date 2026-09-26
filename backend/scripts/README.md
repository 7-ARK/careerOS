# Scripts

Run database migrations before any seed script:

```powershell
python -m alembic upgrade head
python -m scripts.seed_candidate
```

Seed scripts add deterministic demo records only. They do not create or alter
database tables. Schema changes belong in reviewed Alembic revisions.

Optional live embedding check (not part of CI and not part of pytest). It
embeds one sentence with `text-embedding-3-small`, stores it in pgvector, and
prints the hybrid scores. It never prints `OPENAI_API_KEY`.

Set these variables in the environment, not in a committed file:

```text
OPENAI_API_KEY=<your key>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB
RAG_EMBEDDING_MODEL=text-embedding-3-small
```

`DATABASE_URL` must be PostgreSQL with the pgvector extension and the
`evidence_embeddings` table (`python -m alembic upgrade head`). Leave
`RAG_EMBEDDING_DIMENSIONS` unset. `PROVIDER_TIMEOUT_SECONDS` is optional and
defaults to 30. `CAREEROS_PREVIEW_MODE=true` blocks the command.

The application live path is separate: `RAG_EMBEDDING_PROVIDER=openai` plus
`OPENAI_API_KEY`. A missing key fails. `RAG_EMBEDDING_PROVIDER=deterministic`
is the free local mode and does not use the key.

```powershell
python -m scripts.semantic_embedding_smoke
```

The command prints the query, retrieved evidence, lexical score, vector score,
combined retrieval score, observed dimensions, persistence result, API request
count, and an approximate list-price cost, then deletes the temporary smoke
candidate.
