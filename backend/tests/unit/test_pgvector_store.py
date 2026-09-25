"""Persistent pgvector storage and the unchanged local vector index."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.features.resume_intelligence.pgvector_store import (
    PgVectorStore,
    evidence_content_hash,
)
from app.features.resume_intelligence.retrieval import (
    DeterministicHashEmbeddingProvider,
    LocalVectorStore,
)
from app.models import EvidenceEmbedding, User
from app.models.knowledge_base import CandidateProfile
from app.schemas import CandidateEvidence
from tests.support import create_test_engine, create_test_session

DEFAULT_PGVECTOR_URL = (
    "postgresql+psycopg://careeros:change-me-locally@127.0.0.1:5432/careeros_test"
)
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


class CountingProvider:
    """Delegates to feature-hash-v1 and records each embed() call."""

    provider_name = "deterministic_local"
    model_name = "feature-hash-v1"
    dimensions = 256

    def __init__(self) -> None:
        self.inner = DeterministicHashEmbeddingProvider()
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return self.inner.embed(texts)


class FixedEmbeddingProvider:
    """Return caller-supplied vectors so cosine order is independent of hashing."""

    provider_name = "test"
    model_name = "fixed-cosine-v1"
    dimensions = 3

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [list(self.vectors[text]) for text in texts]


def test_content_hash_uses_the_exact_evidence_text() -> None:
    assert evidence_content_hash("FastAPI") == hashlib.sha256(b"FastAPI").hexdigest()
    assert evidence_content_hash("FastAPI") != evidence_content_hash("fastapi")


def test_local_vector_store_still_functions() -> None:
    matched = _evidence("project-local-fastapi", "Implemented FastAPI endpoints and PostgreSQL.")
    other = _evidence(
        "education-local-degree",
        "Bachelor of Computer Science.",
        category="education",
    )
    store = LocalVectorStore(DeterministicHashEmbeddingProvider())
    store.index([other, matched])

    found = store.search("FastAPI backend API", top_k=2)
    projects = store.search("FastAPI backend API", top_k=2, categories={"project"})

    assert found[0].evidence_id == matched.evidence_id
    assert found[0].lexical_score > 0
    assert found[0].vector_score >= 0
    assert [item.evidence_id for item in projects] == [matched.evidence_id]
    assert projects[0].source == "candidate_profile"
    assert projects[0].verified is True


def test_sqlite_schema_creates_embeddings_and_store_requires_postgres() -> None:
    engine = create_test_engine()
    session = create_test_session(engine)
    try:
        assert inspect(engine).has_table("evidence_embeddings")
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            PgVectorStore(session, DeterministicHashEmbeddingProvider())
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_engine() -> Iterator[Engine]:
    explicit = os.environ.get("PGVECTOR_TEST_URL")
    url = explicit or DEFAULT_PGVECTOR_URL
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.commit()
    except Exception as exc:
        engine.dispose()
        if explicit:
            raise
        pytest.skip(f"PostgreSQL with pgvector is not available: {exc}")
    _alembic(url, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(pgvector_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=pgvector_engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with factory() as cleanup:
            cleanup.execute(text("DELETE FROM users WHERE email LIKE 'pgvector-%@example.com'"))
            cleanup.commit()


def test_pgvector_record_persists(db: Session, pgvector_engine: Engine) -> None:
    provider = CountingProvider()
    profile = _profile(db, "pgvector-persist@example.com")
    source_id = uuid4()
    evidence = _evidence(
        f"project-{source_id}",
        "Built a FastAPI service backed by PostgreSQL.",
        source_id=source_id,
        metadata={"label": "CareerOS", "github_url": "https://example.com/careeros"},
    )
    result = PgVectorStore(db, provider).index(profile.id, [evidence])
    db.commit()

    factory = sessionmaker(bind=pgvector_engine, expire_on_commit=False)
    with factory() as verify:
        row = verify.scalars(_embeddings_for(profile.id)).one()
        assert result.embedded == 1
        assert result.reused == 0
        assert row.evidence_id == evidence.evidence_id
        assert row.candidate_profile_id == profile.id
        assert row.source_id == source_id
        assert row.category == "project"
        assert row.text == evidence.text
        assert row.evidence_metadata["github_url"] == "https://example.com/careeros"
        assert row.embedding_model == "feature-hash-v1"
        assert row.embedding_dimensions == 256
        assert len(row.embedding) == 256
        assert row.content_hash == evidence_content_hash(evidence.text)
        assert row.created_at is not None
        assert row.updated_at is not None


def test_retrieval_after_persistence(db: Session, pgvector_engine: Engine) -> None:
    provider = DeterministicHashEmbeddingProvider()
    profile = _profile(db, "pgvector-retrieve@example.com")
    evidence = _evidence("skill-retrieve", "Python, FastAPI, and PostgreSQL.")
    PgVectorStore(db, provider).index(profile.id, [evidence])
    db.commit()

    factory = sessionmaker(bind=pgvector_engine, expire_on_commit=False)
    with factory() as verify:
        found = PgVectorStore(verify, provider).search(
            "FastAPI",
            candidate_profile_id=profile.id,
            top_k=3,
        )

    assert [item.evidence_id for item in found] == ["skill-retrieve"]
    assert found[0].text == evidence.text
    assert found[0].vector_score > 0


def test_top_k_limits_results(db: Session) -> None:
    provider = _axis_provider()
    profile = _profile(db, "pgvector-topk@example.com")
    items = _axis_evidence(include_education=True)
    PgVectorStore(db, provider).index(profile.id, items)

    store = PgVectorStore(db, provider)
    top_two = store.search(
        "query",
        candidate_profile_id=profile.id,
        top_k=2,
        query_embedding=[1.0, 0.0, 0.0],
    )
    only_projects = store.search(
        "query",
        candidate_profile_id=profile.id,
        top_k=4,
        categories={"project"},
        query_embedding=[1.0, 0.0, 0.0],
    )

    assert [item.evidence_id for item in top_two] == ["evidence-near", "evidence-mid"]
    assert len(only_projects) == 4
    assert "evidence-education" not in {item.evidence_id for item in only_projects}


def test_cosine_ordering_uses_exact_similarity(db: Session) -> None:
    provider = _axis_provider()
    profile = _profile(db, "pgvector-cosine@example.com")
    PgVectorStore(db, provider).index(profile.id, _axis_evidence())

    ranked = PgVectorStore(db, provider).search(
        "query",
        candidate_profile_id=profile.id,
        top_k=4,
        query_embedding=[1.0, 0.0, 0.0],
    )

    assert [item.evidence_id for item in ranked] == [
        "evidence-near",
        "evidence-mid",
        "evidence-orthogonal",
        "evidence-opposite",
    ]
    assert ranked[0].vector_score == Decimal("1.0000")
    assert ranked[1].vector_score == Decimal("0.6000")
    assert ranked[2].vector_score == Decimal("0.0000")
    assert ranked[3].vector_score == Decimal("0.0000")
    assert ranked[0].retrieval_score == ranked[0].vector_score
    assert ranked[0].lexical_score == Decimal("0.0000")
    assert all(item.why_retrieved.startswith("Exact cosine similarity") for item in ranked)


def test_candidate_isolation(db: Session) -> None:
    provider = FixedEmbeddingProvider(
        {
            "alpha only": [0.0, 1.0, 0.0],
            "beta only": [1.0, 0.0, 0.0],
        }
    )
    profile_a = _profile(db, "pgvector-a@example.com")
    profile_b = _profile(db, "pgvector-b@example.com")
    alpha = _evidence("profile-a-summary", "alpha only", category="profile")
    beta = _evidence("profile-b-summary", "beta only", category="profile")
    store = PgVectorStore(db, provider)
    store.index(profile_a.id, [alpha])
    store.index(profile_b.id, [beta])
    with pytest.raises(ValueError, match="different candidate"):
        store.index(profile_b.id, [alpha])

    seen_by_a = store.search(
        "beta only",
        candidate_profile_id=profile_a.id,
        top_k=5,
        query_embedding=[1.0, 0.0, 0.0],
    )
    seen_by_b = store.search(
        "beta only",
        candidate_profile_id=profile_b.id,
        top_k=5,
        query_embedding=[1.0, 0.0, 0.0],
    )
    store.index(profile_a.id, [])
    seen_by_b_after = store.search(
        "beta only",
        candidate_profile_id=profile_b.id,
        top_k=5,
        query_embedding=[1.0, 0.0, 0.0],
    )

    assert [item.evidence_id for item in seen_by_a] == ["profile-a-summary"]
    assert seen_by_a[0].vector_score == Decimal("0.0000")
    assert [item.evidence_id for item in seen_by_b] == ["profile-b-summary"]
    assert seen_by_b[0].vector_score == Decimal("1.0000")
    assert [item.evidence_id for item in seen_by_b_after] == ["profile-b-summary"]


def test_stable_evidence_ids(db: Session) -> None:
    provider = DeterministicHashEmbeddingProvider()
    profile = _profile(db, "pgvector-ids@example.com")
    source_id = uuid4()
    evidence = _evidence(
        f"experience-{source_id}",
        "Backend engineer at Example.",
        source_id=source_id,
        category="experience",
        metadata={"label": "Backend engineer at Example"},
    )
    PgVectorStore(db, provider).index(profile.id, [evidence])

    found = PgVectorStore(db, provider).search(
        "backend engineer",
        candidate_profile_id=profile.id,
        top_k=1,
    )

    assert found[0].evidence_id == f"experience-{source_id}"
    assert found[0].source_id == source_id
    assert found[0].category == "experience"
    assert found[0].source == "candidate_profile"
    assert found[0].verified is True
    assert found[0].text == evidence.text
    assert found[0].metadata == {"label": "Backend engineer at Example"}


def test_content_hash_cache_skips_unchanged_text(db: Session) -> None:
    provider = CountingProvider()
    profile = _profile(db, "pgvector-cache@example.com")
    first = _evidence("skill-cache", "PostgreSQL")
    second = _evidence("project-cache", "FastAPI")
    store = PgVectorStore(db, provider)

    initial = store.index(profile.id, [first, second])
    repeated = store.index(profile.id, [first, second])
    relabeled = first.model_copy(update={"metadata": {"label": "Database"}})
    metadata_only = store.index(profile.id, [relabeled, second])
    changed = relabeled.model_copy(update={"text": "PostgreSQL and pgvector"})
    edited = store.index(profile.id, [changed, second])
    changed_row = db.scalars(_embeddings_for(profile.id, evidence_id="skill-cache")).one()
    removed = store.index(profile.id, [second])
    remaining = list(db.scalars(_embeddings_for(profile.id)))

    assert initial.embedded == 2 and initial.reused == 0
    assert repeated.embedded == 0 and repeated.reused == 2
    assert metadata_only.embedded == 0 and metadata_only.reused == 2
    assert provider.batches == [[first.text, second.text], [changed.text]]
    assert edited.embedded == 1 and edited.reused == 1
    assert changed_row.content_hash == evidence_content_hash(changed.text)
    assert changed_row.evidence_metadata == {"label": "Database"}
    assert removed.embedded == 0 and removed.reused == 1
    assert [row.evidence_id for row in remaining] == ["project-cache"]


def test_metadata_only_update_keeps_embedding(db: Session) -> None:
    provider = CountingProvider()
    profile = _profile(db, "pgvector-metadata@example.com")
    evidence = _evidence("skill-meta", "Python", metadata={"label": "Before"})
    store = PgVectorStore(db, provider)
    store.index(profile.id, [evidence])
    updated = evidence.model_copy(update={"metadata": {"label": "After"}})
    store.index(profile.id, [updated])

    row = db.scalars(_embeddings_for(profile.id)).one()
    assert row.evidence_metadata == {"label": "After"}
    assert row.content_hash == evidence_content_hash("Python")
    assert len(provider.batches) == 1


def test_vector_dimension_check_rejects_mismatch(db: Session) -> None:
    profile = _profile(db, "pgvector-dims@example.com")
    db.add(
        EvidenceEmbedding(
            evidence_id="bad-dims",
            candidate_profile_id=profile.id,
            source_id=uuid4(),
            category="skill",
            source="candidate_profile",
            text="mismatched width",
            evidence_metadata={},
            embedding=[1.0, 0.0, 0.0],
            embedding_dimensions=4,
            embedding_model="feature-hash-v1",
            content_hash="b" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_provider_dimension_mismatch_is_rejected(db: Session) -> None:
    class ShortProvider:
        provider_name = "test"
        model_name = "feature-hash-v1"
        dimensions = 256

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0, 0.0] for _text in texts]

    profile = _profile(db, "pgvector-short@example.com")
    store = PgVectorStore(db, ShortProvider())
    with pytest.raises(ValueError, match="configured dimensions"):
        store.index(profile.id, [_evidence("skill-short", "Python")])
    assert list(db.scalars(_embeddings_for(profile.id))) == []


def test_migration_upgrade_and_downgrade(pgvector_engine: Engine) -> None:
    url = pgvector_engine.url.render_as_string(hide_password=False)
    assert _has_table(pgvector_engine, "evidence_embeddings")
    pgvector_engine.dispose()
    try:
        _alembic(url, "-1", downgrade=True)
        assert not _has_table(pgvector_engine, "evidence_embeddings")
        with pgvector_engine.connect() as connection:
            extension = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        assert extension == 1
    finally:
        _alembic(url, "head")
    assert _has_table(pgvector_engine, "evidence_embeddings")
    with pgvector_engine.connect() as connection:
        definition = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_evidence_embeddings_vector_dims'"
            )
        ).scalar()
    assert definition is not None
    assert "vector_dims" in definition


def _alembic(url: str, revision: str, *, downgrade: bool = False) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        config = Config(str(ALEMBIC_INI))
        if downgrade:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _has_table(engine: Engine, name: str) -> bool:
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :name"),
            {"name": name},
        ).scalar()
    return found is not None


def _profile(session: Session, email: str) -> CandidateProfile:
    user = User(email=email, password_hash="test-hash", full_name="PgVector Test")
    session.add(user)
    session.flush()
    profile = CandidateProfile(user_id=user.id, full_name="PgVector Test")
    session.add(profile)
    session.flush()
    return profile


def _evidence(
    evidence_id: str,
    text_value: str,
    *,
    source_id: UUID | None = None,
    category: str = "project",
    metadata: dict[str, str] | None = None,
) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_id=evidence_id,
        source_id=source_id or uuid4(),
        category=category,
        text=text_value,
        metadata=metadata or {"label": evidence_id},
    )


def _axis_provider() -> FixedEmbeddingProvider:
    return FixedEmbeddingProvider(
        {
            "near": [1.0, 0.0, 0.0],
            "mid": [3.0, 4.0, 0.0],
            "orthogonal": [0.0, 1.0, 0.0],
            "opposite": [-1.0, 0.0, 0.0],
            "education": [0.0, 0.0, 1.0],
        }
    )


def _axis_evidence(*, include_education: bool = False) -> list[CandidateEvidence]:
    items = [
        _evidence("evidence-orthogonal", "orthogonal"),
        _evidence("evidence-opposite", "opposite"),
        _evidence("evidence-mid", "mid"),
        _evidence("evidence-near", "near"),
    ]
    if include_education:
        items.append(_evidence("evidence-education", "education", category="education"))
    return items


def _embeddings_for(profile_id: UUID, evidence_id: str | None = None):
    statement = select(EvidenceEmbedding).where(
        EvidenceEmbedding.candidate_profile_id == profile_id
    )
    if evidence_id is not None:
        statement = statement.where(EvidenceEmbedding.evidence_id == evidence_id)
    return statement.order_by(EvidenceEmbedding.evidence_id)
