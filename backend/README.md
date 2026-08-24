# careerOS Backend

FastAPI, Pydantic, SQLAlchemy, Alembic, deterministic evidence retrieval, grounded resume generation, DOCX/PDF export, and application tracking for the [careerOS Golden Career Analysis Flow](../README.md).

## Start locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m scripts.seed_candidate
python -m uvicorn app.main:app --reload --port 8000
```

`DATABASE_URL` is required for local startup. Copy the root `.env.example` values into an ignored environment file or set them in the shell. The deterministic defaults require no provider key.

Use `python -m alembic revision --autogenerate -m "description"` for future schema changes and review every generated migration before applying it. Runtime application startup does not call `Base.metadata.create_all`.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m compileall -q .
```

OpenAPI is served at `http://127.0.0.1:8000/docs` and health at `/health`.
