"""One live OpenAI embedding smoke test. Not part of CI or the pytest suite.

From ``backend/``:

    OPENAI_API_KEY=... \\
    DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB \\
    RAG_EMBEDDING_MODEL=text-embedding-3-small \\
    python -m scripts.semantic_embedding_smoke

Required environment:

- ``OPENAI_API_KEY``: live key. The command exits before any API call when it is missing.
- ``DATABASE_URL``: PostgreSQL URL. The database must have pgvector and the
  ``evidence_embeddings`` table (``python -m alembic upgrade head``).

Optional environment:

- ``RAG_EMBEDDING_MODEL``: defaults to ``text-embedding-3-small``. Leave
  ``RAG_EMBEDDING_DIMENSIONS`` unset so the API returns that model's default width.
- ``PROVIDER_TIMEOUT_SECONDS``: defaults to 30.

``CAREEROS_PREVIEW_MODE=true`` disables the command. The script does not read
``RAG_EMBEDDING_PROVIDER``; the app itself still requires
``RAG_EMBEDDING_PROVIDER=openai`` plus the key, and fails if the key is missing.
The command embeds one evidence sentence, stores it, reads the row back, prints
the hybrid scores, and deletes the temporary candidate. It never prints the key.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import create_database_engine, create_session_factory
from app.features.resume_intelligence.pgvector_store import PgVectorStore
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    OpenAIEmbeddingProvider,
)
from app.models import CandidateProfile, EvidenceEmbedding, Project, User
from app.repositories import CandidateProfileRepository

PYTHON_BACKEND_QUERY = "Python backend development"
FASTAPI_EVIDENCE = "Built REST services using FastAPI."
SMOKE_PROJECTS = (("REST services", FASTAPI_EVIDENCE),)
QUERIES = (PYTHON_BACKEND_QUERY,)
DEFAULT_SMOKE_MODEL = "text-embedding-3-small"
_USD_PER_MILLION_TOKENS = {
    "text-embedding-3-small": Decimal("0.02"),
    "text-embedding-3-large": Decimal("0.13"),
    "text-embedding-ada-002": Decimal("0.10"),
}


@dataclass(frozen=True, slots=True)
class SmokeHit:
    """One retrieved row in the smoke report."""

    query: str
    evidence: str
    lexical_score: str
    vector_score: str
    retrieval_score: str


@dataclass(frozen=True, slots=True)
class SmokeReport:
    """Scores and cache counters for one live embedding run."""

    model_name: str
    dimensions: int
    persisted: str
    embedded: int
    reused: int
    api_requests: int
    prompt_tokens: int
    estimated_cost_usd: str
    hits: tuple[SmokeHit, ...]


def estimate_embedding_cost_usd(model_name: str, prompt_tokens: int) -> Decimal | None:
    """Estimate list-price cost. Unknown models return None instead of a guess."""
    price = _USD_PER_MILLION_TOKENS.get(model_name)
    if price is None:
        return None
    return (price * Decimal(prompt_tokens) / Decimal(1_000_000)).quantize(Decimal("0.00000001"))


def format_smoke_report(report: SmokeReport) -> str:
    """Render the query, evidence, and score components used to tune hybrid weights."""
    lines = [
        "CareerOS semantic embedding smoke",
        f"model: {report.model_name}",
        f"dimensions: {report.dimensions}",
        f"persisted: {report.persisted}",
        f"cache_embedded: {report.embedded}",
        f"cache_reused: {report.reused}",
        f"api_requests: {report.api_requests}",
        f"prompt_tokens: {report.prompt_tokens}",
        f"estimated_cost_usd: {report.estimated_cost_usd}",
        "",
    ]
    for hit in report.hits:
        lines.extend(
            [
                f"query: {hit.query}",
                f"retrieved_evidence: {hit.evidence}",
                f"lexical_score: {hit.lexical_score}",
                f"vector_score: {hit.vector_score}",
                f"retrieval_score: {hit.retrieval_score}",
                "",
            ]
        )
    return "\n".join(lines).rstrip("\n")


def redact_sensitive(message: str, secrets: tuple[str, ...]) -> str:
    """Remove configured secrets from an error string before printing it."""
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def run_smoke(session: Session, provider: OpenAIEmbeddingProvider) -> SmokeReport:
    """Embed, persist, retrieve, and build the report for an open PostgreSQL session."""
    email = f"semantic-smoke-{uuid4()}@example.com"
    session.execute(text("DELETE FROM users WHERE email LIKE 'semantic-smoke-%@example.com'"))
    user = User(email=email, password_hash="smoke-not-a-login", full_name="Semantic Smoke")
    session.add(user)
    session.flush()
    profile = CandidateProfile(user_id=user.id, full_name="Semantic Smoke")
    profile.projects = [
        Project(title=title, description=description, technologies=[], outcomes=[])
        for title, description in SMOKE_PROJECTS
    ]
    session.add(profile)
    session.commit()
    try:
        candidate = CandidateProfileRepository(session).get_complete(profile.id)
        if candidate is None:
            raise RuntimeError("smoke candidate could not be reloaded")
        store = PgVectorStore(session, provider)
        retriever = CandidateEvidenceRetriever(provider, vector_index=store)
        evidence = retriever.collect(candidate)
        first = store.index(candidate.id, evidence)
        second = store.index(candidate.id, evidence)
        session.commit()
        session.expire_all()
        _assert_persisted_rows(session, candidate.id, provider)
        hits: list[SmokeHit] = []
        for query in QUERIES:
            retrieved = retriever.retrieve(candidate, query, top_k=3)
            if not retrieved:
                raise RuntimeError(f"no evidence retrieved for {query}")
            top = retrieved[0]
            hits.append(
                SmokeHit(
                    query=query,
                    evidence=top.text,
                    lexical_score=str(top.lexical_score),
                    vector_score=str(top.vector_score),
                    retrieval_score=str(top.retrieval_score),
                )
            )
        rows = _rows(session, candidate.id)
        cost = estimate_embedding_cost_usd(provider.model_name, provider.usage.prompt_tokens)
        return SmokeReport(
            model_name=rows[0].embedding_model,
            dimensions=rows[0].embedding_dimensions,
            persisted="yes",
            embedded=first.embedded,
            reused=second.reused,
            api_requests=provider.usage.requests,
            prompt_tokens=provider.usage.prompt_tokens,
            estimated_cost_usd="unknown" if cost is None else f"{cost:.8f}",
            hits=tuple(hits),
        )
    finally:
        session.rollback()
        persisted_user = session.get(User, user.id)
        if persisted_user is not None:
            session.delete(persisted_user)
            session.commit()


def main() -> int:
    """Run the live smoke test, or exit 2 before calling OpenAI when config is missing."""
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    secrets = (api_key, database_url)
    if not api_key:
        print("OPENAI_API_KEY is required for the live embedding smoke test.", file=sys.stderr)
        return 2
    if os.environ.get("CAREEROS_PREVIEW_MODE", "").strip().casefold() in {"1", "true", "yes", "on"}:
        print("CAREEROS_PREVIEW_MODE disables live embeddings.", file=sys.stderr)
        return 2
    if not database_url:
        print("DATABASE_URL is required for the live embedding smoke test.", file=sys.stderr)
        return 2
    if not database_url.startswith("postgresql"):
        print("The smoke test requires PostgreSQL with pgvector.", file=sys.stderr)
        return 2
    model_name = os.environ.get("RAG_EMBEDDING_MODEL", DEFAULT_SMOKE_MODEL).strip()
    if not model_name:
        print("RAG_EMBEDDING_MODEL must not be empty.", file=sys.stderr)
        return 2
    try:
        timeout_seconds = int(os.environ.get("PROVIDER_TIMEOUT_SECONDS", "30"))
        dimensions = _optional_dimensions()
    except ValueError as exc:
        print(redact_sensitive(str(exc), secrets), file=sys.stderr)
        return 2
    engine = None
    try:
        engine = create_database_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            extension = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            table = connection.execute(
                text("SELECT to_regclass('public.evidence_embeddings')")
            ).scalar()
        if extension is None:
            print("pgvector is not installed on this database.", file=sys.stderr)
            return 2
        if table is None:
            print("evidence_embeddings is missing. Run alembic upgrade head.", file=sys.stderr)
            return 2
        provider = OpenAIEmbeddingProvider(
            api_key=api_key,
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            dimensions=dimensions,
        )
        factory = create_session_factory(engine)
        with factory() as session:
            report = run_smoke(session, provider)
        print(format_smoke_report(report))
    except Exception as exc:
        print(redact_sensitive(f"{type(exc).__name__}: {exc}", secrets), file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


def _optional_dimensions() -> int | None:
    raw = os.environ.get("RAG_EMBEDDING_DIMENSIONS", "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 1:
        raise ValueError("RAG_EMBEDDING_DIMENSIONS must be a positive integer")
    return value


def _rows(session: Session, profile_id: object) -> list[EvidenceEmbedding]:
    return list(
        session.scalars(
            select(EvidenceEmbedding)
            .where(EvidenceEmbedding.candidate_profile_id == profile_id)
            .order_by(EvidenceEmbedding.evidence_id)
        )
    )


def _assert_persisted_rows(
    session: Session,
    profile_id: object,
    provider: OpenAIEmbeddingProvider,
) -> None:
    rows = _rows(session, profile_id)
    if not rows:
        raise RuntimeError("pgvector did not persist smoke embeddings")
    for row in rows:
        if row.embedding_model != provider.model_name:
            raise RuntimeError("persisted embedding model did not match the OpenAI model")
        if row.embedding_dimensions != provider.dimensions:
            raise RuntimeError("persisted embedding dimensions did not match the OpenAI response")
        stored = f"{row.text} {row.embedding_model} {row.evidence_metadata}"
        if provider.contains_secret(stored):
            raise RuntimeError("API key was written into evidence_embeddings")


if __name__ == "__main__":
    sys.exit(main())
