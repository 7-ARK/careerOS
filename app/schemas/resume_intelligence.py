"""Pydantic contracts for deterministic, evidence-backed resume intelligence."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.enums import MatchQuality, ResumeDraftStatus, ResumeSectionType
from app.schemas.knowledge_base import EntityRead, ReadSchema, SchemaBase


class EvidenceReference(SchemaBase):
    """Trace a recommendation or match back to candidate knowledge-base evidence."""

    source_type: ResumeSectionType
    source_id: UUID
    label: str = Field(min_length=1, max_length=250)
    matched_terms: list[str] = Field(default_factory=list)
    excerpt: str | None = None


class KeywordCoverage(SchemaBase):
    """Explain ATS keyword coverage without rewarding repetition."""

    required_keywords: list[str] = Field(default_factory=list)
    preferred_keywords: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    score: Decimal = Field(ge=0, le=100)


class MatchBreakdown(SchemaBase):
    """Expose deterministic score components and the resulting quality band."""

    overall_match_score: Decimal = Field(ge=0, le=100)
    keyword_match_score: Decimal = Field(ge=0, le=100)
    skills_match_score: Decimal = Field(ge=0, le=100)
    technology_match_score: Decimal = Field(ge=0, le=100)
    experience_match_score: Decimal = Field(ge=0, le=100)
    project_match_score: Decimal = Field(ge=0, le=100)
    education_match_score: Decimal = Field(ge=0, le=100)
    quality: MatchQuality


class ResumeRecommendation(SchemaBase):
    """Recommend a truthful resume change with traceable candidate evidence."""

    section: ResumeSectionType
    recommendation: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    supported_keywords: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ResumeAnalysisBase(SchemaBase):
    """Shared persisted fields for a candidate-job resume analysis."""

    overall_match_score: Decimal = Field(ge=0, le=100)
    keyword_match_score: Decimal = Field(ge=0, le=100)
    skills_match_score: Decimal = Field(ge=0, le=100)
    technology_match_score: Decimal = Field(ge=0, le=100)
    experience_match_score: Decimal = Field(ge=0, le=100)
    project_match_score: Decimal = Field(ge=0, le=100)
    education_match_score: Decimal = Field(ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_technologies: list[str] = Field(default_factory=list)
    missing_technologies: list[str] = Field(default_factory=list)
    relevant_projects: list[EvidenceReference] = Field(default_factory=list)
    relevant_experiences: list[EvidenceReference] = Field(default_factory=list)
    relevant_education: list[EvidenceReference] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    gap_analysis: dict[str, Any] = Field(default_factory=dict)
    tailoring_recommendations: list[ResumeRecommendation] = Field(default_factory=list)
    truthfulness_warnings: list[str] = Field(default_factory=list)
    suggested_resume_summary: str
    suggested_resume_sections: list[ResumeSectionType] = Field(default_factory=list)


class ResumeAnalysisCreate(ResumeAnalysisBase):
    """Create an evidence-backed resume analysis snapshot."""

    candidate_profile_id: UUID
    job_analysis_id: UUID


class ResumeAnalysisUpdate(SchemaBase):
    """Update editable analysis output fields if a review workflow requires it."""

    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    gap_analysis: dict[str, Any] | None = None
    tailoring_recommendations: list[ResumeRecommendation] | None = None
    truthfulness_warnings: list[str] | None = None
    suggested_resume_summary: str | None = None
    suggested_resume_sections: list[ResumeSectionType] | None = None


class ResumeAnalysisRead(EntityRead, ResumeAnalysisCreate):
    """Read a persisted resume analysis snapshot."""


class ResumeAnalysisResult(ReadSchema):
    """Return persisted analysis plus explainable convenience projections."""

    analysis: ResumeAnalysisRead
    keyword_coverage: KeywordCoverage
    match_breakdown: MatchBreakdown


class ResumeDraftBase(SchemaBase):
    """Shared structured content for a truthfulness-safe resume draft."""

    title: str = Field(min_length=1, max_length=250)
    target_role: str = Field(min_length=1, max_length=250)
    summary: str
    skills_section: list[dict[str, Any]] = Field(default_factory=list)
    experience_section: list[dict[str, Any]] = Field(default_factory=list)
    projects_section: list[dict[str, Any]] = Field(default_factory=list)
    education_section: list[dict[str, Any]] = Field(default_factory=list)
    certifications_section: list[dict[str, Any]] = Field(default_factory=list)
    ats_keywords_used: list[str] = Field(default_factory=list)
    omitted_keywords: list[str] = Field(default_factory=list)
    truthfulness_notes: list[str] = Field(default_factory=list)
    status: ResumeDraftStatus | str = ResumeDraftStatus.DRAFT


class ResumeDraftCreate(ResumeDraftBase):
    """Create a structured resume draft from an analysis."""

    resume_analysis_id: UUID
    candidate_profile_id: UUID
    job_analysis_id: UUID


class ResumeDraftUpdate(SchemaBase):
    """Update a structured draft during review."""

    title: str | None = Field(default=None, min_length=1, max_length=250)
    summary: str | None = None
    skills_section: list[dict[str, Any]] | None = None
    experience_section: list[dict[str, Any]] | None = None
    projects_section: list[dict[str, Any]] | None = None
    education_section: list[dict[str, Any]] | None = None
    certifications_section: list[dict[str, Any]] | None = None
    ats_keywords_used: list[str] | None = None
    omitted_keywords: list[str] | None = None
    truthfulness_notes: list[str] | None = None
    status: ResumeDraftStatus | str | None = None


class ResumeDraftRead(EntityRead, ResumeDraftCreate):
    """Read a structured resume draft."""
