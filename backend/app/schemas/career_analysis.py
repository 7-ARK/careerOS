"""Typed contracts for evidence retrieval and the golden career-analysis flow."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.models.enums import (
    CareerAnalysisStage,
    CareerAnalysisStatus,
    DocumentFormat,
    RequirementMatchStatus,
    ResumeTemplateName,
    SourcePlatform,
)
from app.schemas.application_tracking import ApplicationRecordRead
from app.schemas.document_generation import GeneratedDocumentRead
from app.schemas.knowledge_base import ReadSchema, SchemaBase
from app.schemas.resume_intelligence import ResumeDraftRead

RequirementPriority = Literal["required", "preferred", "context"]
RequirementLogic = Literal["all", "any"]
RequirementKind = Literal[
    "skill",
    "technology",
    "responsibility",
    "experience",
    "education",
]


class CandidateEvidence(SchemaBase):
    """One stable, verified candidate fact available to the retrieval layer."""

    evidence_id: str = Field(min_length=1, max_length=250)
    source_id: UUID
    category: str = Field(min_length=1, max_length=80)
    source: Literal["candidate_profile"] = "candidate_profile"
    text: str = Field(min_length=1, max_length=5000)
    verified: Literal[True] = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedCandidateEvidence(CandidateEvidence):
    """Candidate evidence returned by deterministic semantic retrieval."""

    retrieval_score: Decimal = Field(ge=0, le=1)
    lexical_score: Decimal = Field(ge=0, le=1)
    vector_score: Decimal = Field(ge=0, le=1)
    why_retrieved: str = Field(min_length=1)


class JobRequirement(SchemaBase):
    """One typed requirement extracted from a saved job description."""

    requirement_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    kind: RequirementKind
    priority: RequirementPriority
    logic: RequirementLogic = "all"
    alternatives: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_group_logic(self) -> "JobRequirement":
        if self.logic == "any" and len(self.alternatives) < 2:
            raise ValueError("any requirements must provide at least two alternatives")
        if self.logic == "all" and self.alternatives:
            raise ValueError("all requirements cannot provide alternatives")
        return self


class StructuredJobRequirements(SchemaBase):
    """Validated job requirements used by retrieval and matching."""

    job_description_id: UUID
    job_analysis_id: UUID
    job_title: str
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    seniority: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    required_experience: str | None = None
    education_requirements: list[str] = Field(default_factory=list)
    ai_ml_technologies: list[str] = Field(default_factory=list)
    backend_technologies: list[str] = Field(default_factory=list)
    cloud_deployment_requirements: list[str] = Field(default_factory=list)
    important_ats_keywords: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)
    original_job_description: str = Field(min_length=1, max_length=50000)


class RequirementEvidenceMatch(SchemaBase):
    """Explain one job requirement using retrieved candidate evidence."""

    requirement: JobRequirement
    status: RequirementMatchStatus
    supporting_evidence: list[RetrievedCandidateEvidence] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    recommendation: str | None = None


class EvidenceCoverageBreakdown(SchemaBase):
    """Transparent inputs to the code-calculated Evidence Coverage Score."""

    score: Decimal = Field(ge=0, le=100)
    formula: str
    required_weight: Decimal = Decimal("2")
    preferred_weight: Decimal = Decimal("1")
    matched_value: Decimal = Decimal("1")
    partial_value: Decimal = Decimal("0.5")
    earned_weight: Decimal = Field(ge=0)
    possible_weight: Decimal = Field(ge=0)
    matched_count: int = Field(ge=0)
    partially_matched_count: int = Field(ge=0)
    not_evidenced_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)


class MatchExplanation(ReadSchema):
    """Complete evidence-grounded explanation for one candidate and job."""

    candidate_profile_id: UUID
    job_description_id: UUID
    job_analysis_id: UUID
    requirements: StructuredJobRequirements
    requirement_matches: list[RequirementEvidenceMatch]
    evidence_coverage: EvidenceCoverageBreakdown
    overall_fit_summary: str
    strongest_matches: list[str] = Field(default_factory=list)
    partial_matches: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    relevant_projects: list[RetrievedCandidateEvidence] = Field(default_factory=list)
    supported_ats_keywords: list[str] = Field(default_factory=list)
    unsupported_ats_keywords: list[str] = Field(default_factory=list)
    learning_priorities: list[str] = Field(default_factory=list)
    interview_preparation_topics: list[str] = Field(default_factory=list)
    retrieval_provider: str
    embedding_model: str


class MatchExplainRequest(SchemaBase):
    """Select the owned candidate profile used to explain a saved job."""

    candidate_profile_id: UUID
    top_k: int = Field(default=3, ge=1, le=10)


class GroundingValidationResult(ReadSchema):
    """Report whether every generated resume claim cites verified evidence."""

    valid: bool
    checked_claims: int = Field(ge=0)
    cited_claims: int = Field(ge=0)
    citation_coverage: Decimal = Field(ge=0, le=100)
    unsupported_claims: list[str] = Field(default_factory=list)


class PipelineStageRecord(ReadSchema):
    """Inspectable outcome and telemetry for one bounded workflow stage."""

    stage: CareerAnalysisStage
    status: Literal["completed", "failed", "awaiting_review"]
    started_at: datetime
    finished_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    provider: str
    model: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    error: str | None = None
    summary: str | None = None


class GoldenCareerAnalysisRequest(SchemaBase):
    """Start the guaranteed manual-input recruiter demonstration workflow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    candidate_profile_id: UUID
    raw_title: str = Field(min_length=1, max_length=250)
    company_name: str = Field(min_length=1, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: SourcePlatform = SourcePlatform.UNKNOWN
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str = Field(min_length=80, max_length=50000)
    employment_type: str | None = Field(default=None, max_length=100)
    resume_template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS
    top_k: int = Field(default=3, ge=1, le=10)
    mode: Literal["mock", "live"] = "mock"


class GoldenCareerAnalysisRead(ReadSchema):
    """Return the durable state and artifacts for one golden-flow run."""

    id: UUID
    user_id: UUID
    candidate_profile_id: UUID
    job_description_id: UUID | None
    job_analysis_id: UUID | None
    resume_analysis_id: UUID | None
    resume_draft_id: UUID | None
    application_record_id: UUID | None
    status: CareerAnalysisStatus
    current_stage: CareerAnalysisStage
    provider: str
    model_name: str | None
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: Decimal = Field(ge=0)
    started_at: datetime
    finished_at: datetime | None
    structured_requirements: StructuredJobRequirements | None = None
    match_explanation: MatchExplanation | None = None
    evidence_coverage_score: Decimal | None = Field(default=None, ge=0, le=100)
    stages: list[PipelineStageRecord] = Field(default_factory=list)
    error_details: dict[str, Any] | None = None
    review_notes: str | None = None
    resume_draft: ResumeDraftRead | None = None
    application_record: ApplicationRecordRead | None = None
    generated_documents: list[GeneratedDocumentRead] = Field(default_factory=list)
    grounding_validation: GroundingValidationResult | None = None


class GoldenCareerReviewRequest(SchemaBase):
    """Record an explicit human decision before any document export."""

    decision: Literal["approve", "reject"]
    review_notes: str | None = Field(default=None, max_length=2000)
    resume_template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS
    export_formats: list[DocumentFormat] = Field(
        default_factory=lambda: [DocumentFormat.DOCX, DocumentFormat.PDF],
        min_length=1,
        max_length=2,
    )

    @model_validator(mode="after")
    def validate_export_formats(self) -> "GoldenCareerReviewRequest":
        """Allow only one copy of each recruiter-demo document format."""
        if len(set(self.export_formats)) != len(self.export_formats):
            raise ValueError("export_formats must not contain duplicates")
        if DocumentFormat.MARKDOWN in self.export_formats:
            raise ValueError("golden-flow approval exports DOCX and/or PDF")
        return self
