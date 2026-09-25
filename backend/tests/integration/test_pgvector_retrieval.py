"""Golden retrieval through PgVectorStore without replacing hybrid ranking."""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.pgvector_store import PgVectorStore
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
    build_candidate_evidence_retriever,
)
from app.models import EvidenceEmbedding, User
from app.models.enums import RequirementMatchStatus
from app.models.knowledge_base import CandidateProfile, Education, Project, Skill
from app.repositories import CandidateProfileRepository
from app.schemas import GoldenCareerAnalysisRequest, JobRequirement
from app.services.career_analysis import GoldenCareerAnalysisService
from tests.integration.test_golden_career_flow import _golden_request
from tests.unit.test_pgvector_store import CountingProvider
from tests.unit.test_vector_store_selection import IdenticalEmbeddingProvider

DEFAULT_PGVECTOR_URL = (
    "postgresql+psycopg://careeros:change-me-locally@127.0.0.1:5432/careeros_test"
)
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
KNOWN_STATUSES = {
    RequirementMatchStatus.MATCHED,
    RequirementMatchStatus.PARTIALLY_MATCHED,
    RequirementMatchStatus.NOT_EVIDENCED,
    RequirementMatchStatus.NOT_APPLICABLE,
}


@pytest.fixture(scope="module")
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
            cleanup.execute(
                text("DELETE FROM users WHERE email LIKE 'pgvector-phase1b-%@example.com'")
            )
            cleanup.execute(
                text(
                    "DELETE FROM job_descriptions "
                    "WHERE company_name = 'Evidence Labs' AND raw_title = 'Applied AI Engineer'"
                )
            )
            cleanup.commit()


def test_factory_selects_pgvector(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "pgvector")
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)
    retriever = build_candidate_evidence_retriever(
        db,
        provider=DeterministicHashEmbeddingProvider(),
    )
    assert isinstance(retriever.vector_index, PgVectorStore)
    with pytest.raises(TypeError):
        retriever.vector_index.search("FastAPI", top_k=1)


def test_local_and_pgvector_hybrid_scores_match(db: Session) -> None:
    profile = _profile(
        db,
        "pgvector-phase1b-parity@example.com",
        projects=[
            (
                "Cloud deployment",
                "Deployed applications using Google Cloud",
                [],
            )
        ],
    )
    candidate = _load(db, profile.id)
    provider = DeterministicHashEmbeddingProvider()
    local = CandidateEvidenceRetriever(provider)
    persisted = CandidateEvidenceRetriever(provider, vector_index=PgVectorStore(db, provider))

    for query in ("FastAPI", "Python", "PostgreSQL application tracking", "AWS experience"):
        local_hits = local.retrieve(candidate, query, top_k=5)
        persisted_hits = persisted.retrieve(candidate, query, top_k=5)
        assert [item.evidence_id for item in local_hits] == [
            item.evidence_id for item in persisted_hits
        ]
        for left, right in zip(local_hits, persisted_hits, strict=True):
            assert left.lexical_score == right.lexical_score
            assert left.vector_score == right.vector_score
            assert left.retrieval_score == right.retrieval_score
            assert left.evidence_id == right.evidence_id
            assert left.text == right.text

    fastapi_hit = next(
        item for item in persisted.retrieve(candidate, "FastAPI", top_k=5) if "FastAPI" in item.text
    )
    assert fastapi_hit.lexical_score > 0
    assert fastapi_hit.evidence_id.startswith("skill-") or fastapi_hit.evidence_id.startswith(
        "project-"
    )


def test_pgvector_hybrid_score_rejects_identical_vectors_without_lexical_overlap(
    db: Session,
) -> None:
    profile = _profile(
        db,
        "pgvector-phase1b-aws@example.com",
        skills=[],
        projects=[("Cloud deployment", "Deployed applications using Google Cloud", [])],
        education=[],
    )
    candidate = _load(db, profile.id)
    provider = IdenticalEmbeddingProvider()
    retriever = CandidateEvidenceRetriever(provider, vector_index=PgVectorStore(db, provider))
    found = retriever.retrieve(candidate, "AWS experience", top_k=3)
    service = EvidenceMatchService(db, retriever=retriever)
    match = service._match_requirement(
        candidate,
        JobRequirement(
            requirement_id="req-aws-experience",
            text="AWS experience",
            kind="technology",
            priority="required",
        ),
        top_k=3,
    )

    assert found[0].evidence_id == f"project-{candidate.projects[0].id}"
    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score == Decimal("1.0000")
    assert found[0].retrieval_score == Decimal("0.3000")
    assert found[0].why_retrieved.startswith("The deterministic embedding")
    assert match.status == RequirementMatchStatus.NOT_EVIDENCED
    assert match.supporting_evidence == []


def test_match_statuses_and_evidence_ids_match_the_local_store(db: Session) -> None:
    profile = _profile(db, "pgvector-phase1b-status@example.com")
    candidate = _load(db, profile.id)
    provider = DeterministicHashEmbeddingProvider()
    local_service = EvidenceMatchService(
        db,
        retriever=CandidateEvidenceRetriever(provider),
    )
    pg_service = EvidenceMatchService(
        db,
        retriever=CandidateEvidenceRetriever(provider, vector_index=PgVectorStore(db, provider)),
    )
    requirements = [
        _requirement("Python"),
        _requirement("FastAPI services"),
        _requirement("AWS experience"),
    ]

    for requirement in requirements:
        local_match = local_service._match_requirement(candidate, requirement, top_k=3)
        pg_match = pg_service._match_requirement(candidate, requirement, top_k=3)
        assert pg_match.status == local_match.status
        assert pg_match.status in KNOWN_STATUSES
        assert [item.evidence_id for item in pg_match.supporting_evidence] == [
            item.evidence_id for item in local_match.supporting_evidence
        ]
        for item in pg_match.supporting_evidence:
            assert item.evidence_id.startswith(("skill-", "project-", "profile-", "education-"))
            assert item.verified is True

    assert local_service._match_requirement(candidate, requirements[0], top_k=3).status == (
        RequirementMatchStatus.MATCHED
    )
    assert local_service._match_requirement(candidate, requirements[1], top_k=3).status == (
        RequirementMatchStatus.PARTIALLY_MATCHED
    )
    assert local_service._match_requirement(candidate, requirements[2], top_k=3).status == (
        RequirementMatchStatus.NOT_EVIDENCED
    )


def test_candidate_isolation_through_retrieval(db: Session) -> None:
    profile_a = _profile(
        db,
        "pgvector-phase1b-a@example.com",
        skills=[],
        projects=[("Notebooks", "Python notebooks for data analysis", ["Python"])],
        education=[],
    )
    profile_b = _profile(
        db,
        "pgvector-phase1b-b@example.com",
        skills=[],
        projects=[("API", "FastAPI production service", ["FastAPI"])],
        education=[],
    )
    candidate_a = _load(db, profile_a.id)
    candidate_b = _load(db, profile_b.id)
    provider = DeterministicHashEmbeddingProvider()
    store = PgVectorStore(db, provider)
    retriever = CandidateEvidenceRetriever(provider, vector_index=store)

    seen_by_a = retriever.retrieve(candidate_a, "FastAPI", top_k=5)
    seen_by_b = retriever.retrieve(candidate_b, "FastAPI", top_k=5)

    assert {item.evidence_id for item in seen_by_a} == {f"project-{profile_a.projects[0].id}"}
    assert f"project-{profile_b.projects[0].id}" not in {item.evidence_id for item in seen_by_a}
    assert seen_by_b[0].evidence_id == f"project-{profile_b.projects[0].id}"
    assert seen_by_b[0].lexical_score > 0
    stored_ids = set(
        db.scalars(
            select(EvidenceEmbedding.evidence_id).where(
                EvidenceEmbedding.candidate_profile_id == profile_a.id
            )
        )
    )
    assert stored_ids == {f"project-{profile_a.projects[0].id}"}


def test_retrieve_syncs_embeddings_and_skips_unchanged_text(db: Session) -> None:
    profile = _profile(
        db,
        "pgvector-phase1b-sync@example.com",
        skills=[("PostgreSQL", "Databases", Decimal("2"))],
        projects=[("CareerOS", "FastAPI service", ["FastAPI"])],
        education=[],
    )
    provider = CountingProvider()
    retriever = CandidateEvidenceRetriever(provider, vector_index=PgVectorStore(db, provider))
    candidate = _load(db, profile.id)

    retriever.retrieve(candidate, "orchestration-query", top_k=3)
    retriever.retrieve(_load(db, profile.id), "orchestration-query", top_k=3)
    skill = candidate.skills[0]
    skill.name = "PostgreSQL pgvector"
    db.commit()
    changed = _load(db, profile.id)
    retriever.retrieve(changed, "orchestration-query", top_k=3)
    changed.skills.clear()
    db.commit()
    retriever.retrieve(_load(db, profile.id), "orchestration-query", top_k=3)

    evidence_batches = [
        batch for batch in provider.batches if batch != ["orchestration-query"]
    ]
    remaining = list(
        db.scalars(
            select(EvidenceEmbedding).where(EvidenceEmbedding.candidate_profile_id == profile.id)
        )
    )
    assert len(evidence_batches) == 2
    assert any(text_value.startswith("PostgreSQL.") for text_value in evidence_batches[0])
    assert evidence_batches[1] == [
        (
            "PostgreSQL pgvector. Category: Databases. "
            "Candidate-reported experience: 2 years."
        )
    ]
    assert {row.evidence_id for row in remaining} == {f"project-{profile.projects[0].id}"}
    assert all(row.embedding_model == "feature-hash-v1" for row in remaining)


def test_golden_career_analysis_uses_pgvector(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "pgvector")
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "deterministic")
    user, profile = _golden_profile(db)
    request = GoldenCareerAnalysisRequest.model_validate(_golden_request(str(profile.id)))
    result = GoldenCareerAnalysisService(db).start(request, user_id=user.id)
    explanation = result.match_explanation
    assert explanation is not None

    local_explanation = EvidenceMatchService(
        db,
        retriever=CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider()),
    ).explain(profile.id, result.job_description_id)

    assert result.status.value == "awaiting_review"
    assert result.provider == "deterministic_local"
    assert result.model_name == "feature-hash-v1"
    assert result.grounding_validation is not None
    assert result.grounding_validation.valid is True
    assert explanation.evidence_coverage.formula.startswith(
        "100 * earned weight / possible weight"
    )
    assert explanation.evidence_coverage.score == local_explanation.evidence_coverage.score
    assert explanation.evidence_coverage.formula == local_explanation.evidence_coverage.formula
    assert "AWS" in explanation.missing_requirements
    python_match = next(
        match for match in explanation.requirement_matches if match.requirement.text == "Python"
    )
    assert python_match.status == RequirementMatchStatus.MATCHED
    assert python_match.supporting_evidence
    assert all(item.verified is True for item in python_match.supporting_evidence)
    assert all(match.status in KNOWN_STATUSES for match in explanation.requirement_matches)
    pg_outcomes = [
        (
            match.requirement.text,
            match.status,
            [item.evidence_id for item in match.supporting_evidence],
            [
                (item.lexical_score, item.vector_score, item.retrieval_score)
                for item in match.supporting_evidence
            ],
        )
        for match in explanation.requirement_matches
    ]
    local_outcomes = [
        (
            match.requirement.text,
            match.status,
            [item.evidence_id for item in match.supporting_evidence],
            [
                (item.lexical_score, item.vector_score, item.retrieval_score)
                for item in match.supporting_evidence
            ],
        )
        for match in local_explanation.requirement_matches
    ]
    assert pg_outcomes == local_outcomes
    rows = list(
        db.scalars(
            select(EvidenceEmbedding).where(EvidenceEmbedding.candidate_profile_id == profile.id)
        )
    )
    assert rows
    assert {row.embedding_model for row in rows} == {"feature-hash-v1"}
    assert {row.candidate_profile_id for row in rows} == {profile.id}


def _alembic(url: str, revision: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(Config(str(ALEMBIC_INI)), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _golden_profile(session: Session) -> tuple[User, CandidateProfile]:
    user = User(
        email="pgvector-phase1b-golden@example.com",
        password_hash="test-hash",
        full_name="Golden User",
    )
    session.add(user)
    session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Ada Candidate",
        email="ada-pgvector@example.com",
        location="Remote",
        headline="Junior Applied AI Engineer",
        summary="Python engineer building evidence-grounded FastAPI applications.",
    )
    profile.skills = [
        Skill(
            name="Python",
            category="Programming Languages",
            self_rating=4,
            years_of_experience=Decimal("2"),
        ),
        Skill(
            name="FastAPI",
            category="Backend Development",
            self_rating=4,
            years_of_experience=Decimal("1"),
        ),
    ]
    profile.projects = [
        Project(
            title="CareerOS",
            description=(
                "Implemented FastAPI endpoints, deterministic matching, and PostgreSQL "
                "application tracking."
            ),
            technologies=["Python", "FastAPI", "PostgreSQL"],
            outcomes=["Added automated API and document-generation tests."],
            github_url="https://github.com/example/careeros",
        )
    ]
    profile.education = [
        Education(
            institution="Example University",
            degree="BS Computer Science",
            field_of_study="Computer Science",
        )
    ]
    session.add(profile)
    session.commit()
    return user, profile


def _profile(
    session: Session,
    email: str,
    *,
    skills: list[tuple[str, str, Decimal]] | None = None,
    projects: list[tuple[str, str, list[str]]] | None = None,
    education: list[tuple[str, str]] | None = None,
) -> CandidateProfile:
    if skills is None:
        skills = [
            ("Python", "Programming Languages", Decimal("2")),
            ("FastAPI", "Backend Development", Decimal("1")),
        ]
    if projects is None:
        projects = [
            (
                "CareerOS",
                "Implemented FastAPI endpoints and PostgreSQL application tracking.",
                ["Python", "FastAPI", "PostgreSQL"],
            )
        ]
    if education is None:
        education = [("Example University", "BS Computer Science")]
    user = User(email=email, password_hash="test-hash", full_name="Phase 1B")
    session.add(user)
    session.flush()
    profile = CandidateProfile(user_id=user.id, full_name="Phase 1B")
    profile.skills = [
        Skill(
            name=name,
            category=category,
            self_rating=4,
            years_of_experience=years,
        )
        for name, category, years in skills
    ]
    profile.projects = [
        Project(title=title, description=description, technologies=technologies, outcomes=[])
        for title, description, technologies in projects
    ]
    profile.education = [
        Education(institution=institution, degree=degree, field_of_study="Computer Science")
        for institution, degree in education
    ]
    session.add(profile)
    session.commit()
    return profile


def _load(session: Session, profile_id: UUID) -> CandidateProfile:
    candidate = CandidateProfileRepository(session).get_complete(profile_id)
    assert candidate is not None
    return candidate


def _requirement(text: str) -> JobRequirement:
    return JobRequirement(
        requirement_id=f"req-{uuid4()}",
        text=text,
        kind="technology",
        priority="required",
    )
