"""Semantic retrieval with a mock provider. No OpenAI calls."""

from decimal import Decimal
from uuid import uuid4

from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    LocalVectorStore,
)
from app.models import CandidateProfile, Project
from app.models.enums import RequirementMatchStatus
from app.schemas import CandidateEvidence, JobRequirement
from tests.semantic_embeddings import (
    AWS_QUERY,
    FASTAPI_EVIDENCE,
    GCP_EVIDENCE,
    POSTGRES_EVIDENCE,
    PYTHON_BACKEND_QUERY,
    RELATIONAL_QUERY,
    UNRELATED_EVIDENCE,
    SemanticMockEmbeddingProvider,
    expected_hybrid_score,
)


def test_python_backend_query_retrieves_fastapi_without_lexical_overlap() -> None:
    found = _search(PYTHON_BACKEND_QUERY)

    assert FASTAPI_EVIDENCE in found[0].text
    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score >= Decimal("0.9000")
    assert found[0].retrieval_score == expected_hybrid_score(
        found[0].lexical_score,
        found[0].vector_score,
    )
    assert found[0].why_retrieved == "The embedding ranked this verified evidence as related."
    assert all(FASTAPI_EVIDENCE not in item.text for item in found[1:])


def test_relational_database_query_retrieves_postgresql_without_lexical_overlap() -> None:
    found = _search(RELATIONAL_QUERY)

    assert POSTGRES_EVIDENCE in found[0].text
    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score >= Decimal("0.7000")
    assert found[0].retrieval_score == expected_hybrid_score(
        found[0].lexical_score,
        found[0].vector_score,
    )
    assert POSTGRES_EVIDENCE not in found[1].text


def test_high_semantic_similarity_does_not_claim_aws_from_google_cloud() -> None:
    provider = SemanticMockEmbeddingProvider()
    candidate = _google_cloud_candidate()
    retriever = CandidateEvidenceRetriever(provider)
    found = retriever.retrieve(candidate, AWS_QUERY, top_k=3)
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = retriever
    match = service._match_requirement(candidate, _requirement(AWS_QUERY), top_k=3)

    assert GCP_EVIDENCE in found[0].text
    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score == Decimal("1.0000")
    assert found[0].retrieval_score == Decimal("0.3000")
    assert match.status == RequirementMatchStatus.NOT_EVIDENCED
    assert match.supporting_evidence == []


def _search(query: str):
    evidence = [
        _evidence("evidence-art", UNRELATED_EVIDENCE),
        _evidence("evidence-gcp", GCP_EVIDENCE),
        _evidence("evidence-postgres", POSTGRES_EVIDENCE),
        _evidence("evidence-fastapi", FASTAPI_EVIDENCE),
    ]
    store = LocalVectorStore(SemanticMockEmbeddingProvider())
    store.index(evidence)
    return store.search(query, top_k=4)


def _evidence(evidence_id: str, text: str) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_id=evidence_id,
        source_id=uuid4(),
        category="project",
        text=text,
        metadata={"label": evidence_id},
    )


def _google_cloud_candidate() -> CandidateProfile:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Cloud Candidate")
    candidate.projects = [
        Project(
            id=uuid4(),
            title="Cloud deployment",
            description=GCP_EVIDENCE,
            technologies=[],
            outcomes=[],
        )
    ]
    return candidate


def _requirement(text: str) -> JobRequirement:
    return JobRequirement(
        requirement_id="req-aws-experience",
        text=text,
        kind="technology",
        priority="required",
    )
