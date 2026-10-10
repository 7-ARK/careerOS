"""Persistence models for evidence-backed resume intelligence."""

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ResumeDraftStatus

if TYPE_CHECKING:
    from app.models.document_generation import GeneratedDocument
    from app.models.job_analysis import JobAnalysis
    from app.models.knowledge_base import CandidateProfile


class ResumeAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist an explainable candidate-job analysis snapshot."""

    __tablename__ = "resume_analyses"
    __table_args__ = (
        CheckConstraint(
            "overall_match_score >= 0 AND overall_match_score <= 100",
            name="overall_match_score_range",
        ),
        CheckConstraint(
            "keyword_match_score >= 0 AND keyword_match_score <= 100",
            name="keyword_match_score_range",
        ),
        CheckConstraint(
            "skills_match_score >= 0 AND skills_match_score <= 100",
            name="skills_match_score_range",
        ),
        CheckConstraint(
            "technology_match_score >= 0 AND technology_match_score <= 100",
            name="technology_match_score_range",
        ),
        CheckConstraint(
            "experience_match_score >= 0 AND experience_match_score <= 100",
            name="experience_match_score_range",
        ),
        CheckConstraint(
            "project_match_score >= 0 AND project_match_score <= 100",
            name="project_match_score_range",
        ),
        CheckConstraint(
            "education_match_score >= 0 AND education_match_score <= 100",
            name="education_match_score_range",
        ),
        Index(
            "ix_resume_analyses_candidate_job_created",
            "candidate_profile_id",
            "job_analysis_id",
            "created_at",
        ),
    )

    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    keyword_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    skills_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    technology_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    experience_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    project_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    education_match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    relevant_projects: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    relevant_experiences: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    relevant_education: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gap_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tailoring_recommendations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    truthfulness_warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    suggested_resume_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_resume_sections: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="resume_analyses")
    job_analysis: Mapped["JobAnalysis"] = relationship(back_populates="resume_analyses")
    drafts: Mapped[list["ResumeDraft"]] = relationship(
        back_populates="resume_analysis", cascade="all, delete-orphan"
    )


class ResumeDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist a structured, truthfulness-safe resume draft."""

    __tablename__ = "resume_drafts"
    __table_args__ = (
        Index("ix_resume_drafts_candidate_created", "candidate_profile_id", "created_at"),
        Index("ix_resume_drafts_job_created", "job_analysis_id", "created_at"),
        Index("ix_resume_drafts_analysis_created", "resume_analysis_id", "created_at"),
    )

    resume_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    target_role: Mapped[str] = mapped_column(String(250), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    skills_section: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    experience_section: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    projects_section: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    education_section: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    certifications_section: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    ats_keywords_used: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    omitted_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    truthfulness_notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    grounding_manifest: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ResumeDraftStatus.DRAFT, index=True
    )

    resume_analysis: Mapped[ResumeAnalysis] = relationship(back_populates="drafts")
    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="resume_drafts")
    job_analysis: Mapped["JobAnalysis"] = relationship(back_populates="resume_drafts")
    generated_documents: Mapped[list["GeneratedDocument"]] = relationship(
        back_populates="resume_draft", cascade="all, delete-orphan"
    )
