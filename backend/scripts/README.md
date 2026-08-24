# Scripts

Run database migrations before any seed script:

```powershell
python -m alembic upgrade head
python -m scripts.seed_candidate
```

Seed scripts add deterministic demo records only. They do not create or alter
database tables. Schema changes belong in reviewed Alembic revisions.
