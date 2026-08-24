"""Focused tests for transparent retrieval and code-calculated coverage."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
    LocalVectorStore,
)
from app.models import CandidateProfile, Education, Skill, WorkExperience
from app.models.enums import RequirementMatchStatus
from app.schemas import CandidateEvidence, JobRequirement, RequirementEvidenceMatch


def test_local_vector_store_is_deterministic_and_honors_category_filter() -> None:
    fastapi = CandidateEvidence(
        evidence_id="project-careeros-001",
        source_id=uuid4(),
        category="project",
        text="Implemented FastAPI endpoints and PostgreSQL application tracking.",
    )
    degree = CandidateEvidence(
        evidence_id="education-cs-001",
        source_id=uuid4(),
        category="education",
        text="Bachelor of Computer Science.",
    )
    store = LocalVectorStore(DeterministicHashEmbeddingProvider())
    store.index([degree, fastapi])

    first = store.search("FastAPI backend API", top_k=2)
    second = store.search("FastAPI backend API", top_k=2)
    projects = store.search("FastAPI backend API", top_k=2, categories={"project"})

    assert [item.evidence_id for item in first] == [item.evidence_id for item in second]
    assert first[0].evidence_id == fastapi.evidence_id
    assert first[0].retrieval_score > first[1].retrieval_score
    assert [item.evidence_id for item in projects] == [fastapi.evidence_id]
    assert projects[0].source == "candidate_profile"
    assert projects[0].verified is True


def test_evidence_coverage_uses_documented_weighted_formula() -> None:
    matches = [
        _match("Python", "required", RequirementMatchStatus.MATCHED),
        _match("FastAPI", "required", RequirementMatchStatus.PARTIALLY_MATCHED),
        _match("Docker", "preferred", RequirementMatchStatus.NOT_EVIDENCED),
        _match("Collaborate", "context", RequirementMatchStatus.MATCHED),
    ]

    coverage = EvidenceMatchService.calculate_coverage(matches)

    assert coverage.earned_weight == Decimal("3")
    assert coverage.possible_weight == Decimal("5")
    assert coverage.score == Decimal("60.00")
    assert coverage.matched_count == 2
    assert coverage.partially_matched_count == 1
    assert coverage.not_evidenced_count == 1
    assert "required requirements weigh 2" in coverage.formula


def test_any_requirement_matches_one_supported_alternative() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.skills = [
        Skill(
            id=uuid4(),
            name="Flask",
            category="Backend",
            self_rating=3,
            years_of_experience=Decimal("1"),
        )
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()
    requirement = JobRequirement(
        requirement_id="req-framework",
        text="Django or Flask",
        kind="technology",
        priority="preferred",
        logic="any",
        alternatives=["Django", "Flask"],
    )

    match = service._match_requirement(candidate, requirement, top_k=3)

    assert match.status == RequirementMatchStatus.MATCHED
    assert "Flask" in match.explanation


def test_semantic_aliases_recover_git_human_review_and_llm_evidence() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.skills = [
        Skill(
            id=uuid4(),
            name="LangGraph",
            category="AI Engineering",
            self_rating=3,
            years_of_experience=Decimal("1"),
        )
    ]
    candidate.work_experiences = [
        WorkExperience(
            id=uuid4(),
            company="Example",
            job_title="Developer",
            start_date=date(2024, 1, 1),
            is_current=True,
            achievements=[
                "Added GitHub pull-request workflows.",
                "Preserved human review checkpoints in automated workflows.",
            ],
        )
    ]
    candidate.education = [
        Education(
            id=uuid4(),
            institution="Example University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
        )
    ]
    retriever = CandidateEvidenceRetriever()
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = retriever

    assert service._match_requirement(
        candidate, _requirement("Git", "technology"), top_k=3
    ).status == RequirementMatchStatus.MATCHED
    assert service._match_requirement(
        candidate, _requirement("Human-in-the-loop workflow", "skill"), top_k=3
    ).status in {RequirementMatchStatus.MATCHED, RequirementMatchStatus.PARTIALLY_MATCHED}
    assert service._match_requirement(
        candidate, _requirement("Large Language Models", "skill"), top_k=3
    ).status == RequirementMatchStatus.PARTIALLY_MATCHED
    education_group = JobRequirement(
        requirement_id="req-degree",
        text="AI, Computer Science, Machine Learning, or related field",
        kind="education",
        priority="required",
        logic="any",
        alternatives=["Artificial Intelligence", "Computer Science", "Machine Learning"],
    )
    assert service._match_requirement(
        candidate, education_group, top_k=3
    ).status == RequirementMatchStatus.MATCHED


def test_canonical_bullets_are_the_only_scoreable_requirements() -> None:
    analysis_id = uuid4()
    canonical = [
        {
            "text": "Build validated REST API endpoints using FastAPI and Pydantic models.",
            "kind": "technology",
            "priority": "required",
            "logic": "all",
            "alternatives": [],
        },
        {
            "text": "Experience with Django or Flask.",
            "kind": "technology",
            "priority": "preferred",
            "logic": "any",
            "alternatives": ["Django", "Flask"],
        },
    ]
    analysis = SimpleNamespace(
        id=analysis_id,
        match_relevant_signals={"canonical_requirements": canonical},
        required_skills=["APIs"],
        preferred_skills=[],
        required_technologies=["FastAPI"],
        preferred_technologies=["Django", "Flask"],
        responsibilities=["Build validated REST API endpoints."],
        estimated_years_min=None,
        qualifications=[],
        normalized_title="Applied AI Engineer",
        seniority_level="junior",
        ats_keywords=["FastAPI", "APIs", "Django", "Flask"],
    )
    job = SimpleNamespace(
        id=uuid4(),
        company_name="Example",
        location="Remote",
        employment_type=None,
        description_text="Fixture",
    )

    structured = EvidenceMatchService.structured_requirements(job, analysis)

    assert [item.text for item in structured.requirements] == [
        canonical[0]["text"],
        canonical[1]["text"],
    ]
    assert [item.priority for item in structured.requirements] == ["required", "preferred"]
    assert structured.requirements[1].logic == "any"
    assert all(item.text not in {"FastAPI", "APIs"} for item in structured.requirements)


def test_cloud_tools_require_explicit_candidate_evidence() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.skills = [
        Skill(
            id=uuid4(),
            name="Docker",
            category="Developer Tools",
            self_rating=4,
            years_of_experience=Decimal("2"),
        ),
        Skill(
            id=uuid4(),
            name="FastAPI",
            category="Backend",
            self_rating=4,
            years_of_experience=Decimal("2"),
        ),
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()

    for term in ("AWS", "Kubernetes", "CI/CD"):
        match = service._match_requirement(candidate, _requirement(term, "technology"), top_k=3)
        assert match.status == RequirementMatchStatus.NOT_EVIDENCED
        assert match.supporting_evidence == []


def test_cloud_tools_accept_only_explicit_names_or_conservative_aliases() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.skills = [
        Skill(
            id=uuid4(),
            name="Amazon Web Services",
            category="Cloud",
            self_rating=3,
            years_of_experience=Decimal("1"),
        ),
        Skill(
            id=uuid4(),
            name="K8s",
            category="Cloud",
            self_rating=3,
            years_of_experience=Decimal("1"),
        ),
        Skill(
            id=uuid4(),
            name="Continuous integration",
            category="Developer Tools",
            self_rating=3,
            years_of_experience=Decimal("1"),
        ),
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()

    for term in ("AWS", "Kubernetes", "CI/CD"):
        match = service._match_requirement(candidate, _requirement(term, "technology"), top_k=3)
        assert match.status == RequirementMatchStatus.MATCHED
        assert match.supporting_evidence


def test_experience_matching_uses_merged_employment_date_ranges() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.work_experiences = [
        WorkExperience(
            id=uuid4(),
            company="First",
            job_title="Intern",
            start_date=date(2022, 1, 1),
            end_date=date(2023, 1, 1),
            is_current=False,
        ),
        WorkExperience(
            id=uuid4(),
            company="Second",
            job_title="Engineer",
            start_date=date(2022, 7, 1),
            end_date=date(2024, 1, 1),
            is_current=False,
        ),
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()
    requirement = JobRequirement(
        requirement_id="req-experience",
        text="2+ years of professional experience.",
        kind="experience",
        priority="required",
    )

    years = service._candidate_experience_years(candidate, as_of=date(2025, 1, 1))
    match = service._match_requirement(candidate, requirement, top_k=3)

    assert years == Decimal("2.00")
    assert match.status == RequirementMatchStatus.MATCHED
    assert "2.00 years" in match.explanation


def test_experience_range_without_dated_history_is_not_evidenced() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.work_experiences = []
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()
    requirement = JobRequirement(
        requirement_id="req-experience-range",
        text="0-2 years of professional, internship, or substantial project experience.",
        kind="experience",
        priority="required",
    )

    match = service._match_requirement(candidate, requirement, top_k=3)

    assert match.status == RequirementMatchStatus.NOT_EVIDENCED
    assert "No dated employment history" in match.explanation


def test_bounded_experience_range_reports_upper_bound_overage() -> None:
    candidate = CandidateProfile(id=uuid4(), user_id=uuid4(), full_name="Test Candidate")
    candidate.work_experiences = [
        WorkExperience(
            id=uuid4(),
            company="Example",
            job_title="Engineer",
            start_date=date(2021, 1, 1),
            end_date=date(2024, 1, 1),
            is_current=False,
        )
    ]
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever()
    requirement = JobRequirement(
        requirement_id="req-bounded-experience",
        text="0-2 years of professional experience.",
        kind="experience",
        priority="required",
    )

    match = service._match_requirement(candidate, requirement, top_k=3)

    assert match.status == RequirementMatchStatus.PARTIALLY_MATCHED
    assert "exceeds the stated 0-2 year range" in match.explanation


def _match(
    text: str,
    priority: str,
    status: RequirementMatchStatus,
) -> RequirementEvidenceMatch:
    return RequirementEvidenceMatch(
        requirement=JobRequirement(
            requirement_id=f"req-{text.casefold()}",
            text=text,
            kind="skill",
            priority=priority,
        ),
        status=status,
        explanation="Deterministic test fixture.",
    )


def _requirement(text: str, kind: str) -> JobRequirement:
    return JobRequirement(
        requirement_id=f"req-{text.casefold()}",
        text=text,
        kind=kind,
        priority="required",
    )
