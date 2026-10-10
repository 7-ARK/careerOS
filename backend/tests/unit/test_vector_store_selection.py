"""Vector-store selection and the hybrid ranking contract that both stores share."""

from __future__ import annotations

import inspect
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.pgvector_store import PgVectorStore
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
    LocalVectorStore,
    build_candidate_evidence_retriever,
)
from app.models import CandidateProfile, Project, Skill
from app.models.enums import RequirementMatchStatus
from app.schemas import JobRequirement
from tests.support import create_test_engine, create_test_session


class IdenticalEmbeddingProvider:
    """Return one vector for every text so cosine is 1 and lexical score stays independent."""

    provider_name = "identical"
    model_name = "identical-v1"
    dimensions = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, *([0.0] * 31)] for _text in texts]


def test_local_vector_store_remains_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_VECTOR_STORE", raising=False)
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)
    settings = Settings.from_env()
    retriever = build_candidate_evidence_retriever(settings=settings)
    session = _sqlite_session()
    try:
        service = EvidenceMatchService(session)
    finally:
        session.close()

    assert settings.rag_vector_store == "local"
    assert isinstance(retriever.vector_index, LocalVectorStore)
    assert isinstance(service.retriever.vector_index, LocalVectorStore)
    assert isinstance(retriever.provider, DeterministicHashEmbeddingProvider)


def test_config_selects_pgvector_and_rejects_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "pgvector")
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)
    settings = Settings.from_env()
    session = _sqlite_session()
    try:
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            build_candidate_evidence_retriever(session, settings=settings)
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            EvidenceMatchService(session)
    finally:
        session.close()

    assert settings.rag_vector_store == "pgvector"
    with pytest.raises(RuntimeError, match="database session"):
        build_candidate_evidence_retriever(None, settings=settings)
    with pytest.raises(TypeError, match="SQLAlchemy"):
        build_candidate_evidence_retriever(object(), settings=settings)


def test_hand_built_retriever_stays_local_when_config_selects_pgvector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "pgvector")
    retriever = CandidateEvidenceRetriever()
    assert isinstance(retriever.vector_index, LocalVectorStore)


def test_vector_reads_require_a_candidate_scope() -> None:
    for method in (
        PgVectorStore.search,
        PgVectorStore.sync,
        PgVectorStore.load_vectors,
        LocalVectorStore.sync,
    ):
        parameter = inspect.signature(method).parameters["candidate_profile_id"]
        assert parameter.default is inspect.Parameter.empty


def test_aws_experience_is_not_claimed_from_google_cloud() -> None:
    candidate = _google_cloud_candidate()
    requirement = _requirement("AWS experience")
    for provider in (DeterministicHashEmbeddingProvider(), IdenticalEmbeddingProvider()):
        service = EvidenceMatchService.__new__(EvidenceMatchService)
        service.retriever = CandidateEvidenceRetriever(provider)
        match = service._match_requirement(candidate, requirement, top_k=3)
        assert match.status == RequirementMatchStatus.NOT_EVIDENCED
        assert match.supporting_evidence == []


def test_hybrid_score_keeps_lexical_weight_when_vectors_are_identical() -> None:
    candidate = _google_cloud_candidate()
    retriever = CandidateEvidenceRetriever(IdenticalEmbeddingProvider())
    found = retriever.retrieve(candidate, "AWS experience", top_k=3)
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = retriever

    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score == Decimal("1.0000")
    assert found[0].retrieval_score == Decimal("0.3000")
    assert found[0].why_retrieved == "The embedding ranked this verified evidence as related."
    match = service._match_requirement(candidate, _requirement("AWS experience"), top_k=3)
    assert match.status == RequirementMatchStatus.NOT_EVIDENCED
    assert match.supporting_evidence == []
    unrelated = service._match_requirement(candidate, _requirement("Redis caching"), top_k=3)
    assert unrelated.status == RequirementMatchStatus.NOT_EVIDENCED
    assert unrelated.supporting_evidence == []


def test_deterministic_provider_names_its_zero_lexical_reason() -> None:
    found = CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider()).retrieve(
        _google_cloud_candidate(),
        "AWS experience",
        top_k=1,
    )

    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].why_retrieved.startswith("The deterministic embedding")


def test_existing_match_statuses_survive_the_shared_ranker() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Status Candidate")
    candidate.skills = [
        Skill(
            id=uuid4(),
            name="Python",
            category="Programming Languages",
            self_rating=4,
            years_of_experience=Decimal("2"),
        ),
        Skill(
            id=uuid4(),
            name="FastAPI",
            category="Backend",
            self_rating=4,
            years_of_experience=Decimal("1"),
        ),
    ]
    candidate.projects = [
        Project(
            id=uuid4(),
            title="Cloud deployment",
            description="Deployed applications using Google Cloud",
            technologies=[],
            outcomes=[],
        )
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider())

    matched = service._match_requirement(candidate, _requirement("Python"), top_k=3)
    partial = service._match_requirement(candidate, _requirement("FastAPI services"), top_k=3)
    missing = service._match_requirement(candidate, _requirement("AWS experience"), top_k=3)

    assert matched.status == RequirementMatchStatus.MATCHED
    assert matched.supporting_evidence[0].evidence_id == f"skill-{candidate.skills[0].id}"
    assert partial.status == RequirementMatchStatus.PARTIALLY_MATCHED
    assert partial.supporting_evidence[0].evidence_id == f"skill-{candidate.skills[1].id}"
    assert missing.status == RequirementMatchStatus.NOT_EVIDENCED
    assert missing.supporting_evidence == []


def _sqlite_session() -> Session:
    engine = create_test_engine()
    return create_test_session(engine)


def _google_cloud_candidate() -> CandidateProfile:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Cloud Candidate")
    candidate.projects = [
        Project(
            id=uuid4(),
            title="Cloud deployment",
            description="Deployed applications using Google Cloud",
            technologies=[],
            outcomes=[],
        )
    ]
    return candidate


def _requirement(text: str) -> JobRequirement:
    return JobRequirement(
        requirement_id=f"req-{text.casefold().replace(' ', '-')}",
        text=text,
        kind="technology",
        priority="required",
    )
