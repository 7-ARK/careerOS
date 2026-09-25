# Scripts

Run database migrations before any seed script:

```powershell
python -m alembic upgrade head
python -m scripts.seed_candidate
```

Seed scripts add deterministic demo records only. They do not create or alter
database tables. Schema changes belong in reviewed Alembic revisions.

Optional live embedding check (not part of CI). Requires `OPENAI_API_KEY` and a
PostgreSQL `DATABASE_URL` with pgvector. It does not run under pytest.

```powershell
python -m scripts.semantic_embedding_smoke
```

The command prints the query, retrieved evidence, lexical score, vector score,
and combined retrieval score, then deletes the temporary smoke candidate.
