"""Persistence models for captured job descriptions and derived intelligence."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.application_tracking import ApplicationRecord
    from app.models.document_generation import GeneratedDocument
    from app.models.knowledge_base import ApplicationHistory
    from app.models.resume_intelligence import ResumeAnalysis, ResumeDraft


class JobDescription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Captured source job posting before analysis."""

    __tablename__ = "job_descriptions"
    __table_args__ = (
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
        Index("ix_job_descriptions_company_title", "company_name", "raw_title"),
        Index("ix_job_descriptions_platform_location", "source_platform", "location"),
        Index("ix_job_descriptions_created_at", "created_at"),
    )

    raw_title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(250), index=True)
    location: Mapped[str | None] = mapped_column(String(250), index=True)
    source_platform: Mapped[str | None] = mapped_column(String(100), index=True)
    job_url: Mapped[str | None] = mapped_column(String(1000))
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    employment_type: Mapped[str | None] = mapped_column(String(100), index=True)
    workplace_type: Mapped[str | None] = mapped_column(String(100), index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    analyses: Mapped[list["JobAnalysis"]] = relationship(
        back_populates="job_description",
        cascade="all, delete-orphan",
        order_by="JobAnalysis.revision",
    )
    applications: Mapped[list["ApplicationHistory"]] = relationship(
        back_populates="job_description"
    )
    application_records: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="job_description"
    )


class JobAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned machine-readable intelligence derived from a job posting."""

    __tablename__ = "job_analyses"
    __table_args__ = (
        CheckConstraint("revision > 0", name="revision_positive"),
        Index(
            "ix_job_analyses_description_revision",
            "job_description_id",
            "revision",
            unique=True,
        ),
        Index("ix_job_analyses_title_seniority", "normalized_title", "seniority_level"),
        Index("ix_job_analyses_created_at", "created_at"),
        CheckConstraint(
            "estimated_years_min IS NULL OR estimated_years_min >= 0",
            name="estimated_years_min_non_negative",
        ),
        CheckConstraint(
            "estimated_years_max IS NULL OR estimated_years_max >= 0",
            name="estimated_years_max_non_negative",
        ),
        CheckConstraint(
            "estimated_years_min IS NULL OR estimated_years_max IS NULL "
            "OR estimated_years_min <= estimated_years_max",
            name="estimated_years_range",
        ),
    )

    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(nullable=False)
    analyzer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    seniority_level: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    estimated_years_min: Mapped[int | None] = mapped_column(Integer)
    estimated_years_max: Mapped[int | None] = mapped_column(Integer)
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    responsibilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    qualifications: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    soft_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    domain_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ats_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    red_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    job_summary: Mapped[str] = mapped_column(Text, nullable=False)
    match_relevant_signals: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    job_description: Mapped[JobDescription] = relationship(back_populates="analyses")
    resume_analyses: Mapped[list["ResumeAnalysis"]] = relationship(
        back_populates="job_analysis", cascade="all, delete-orphan"
    )
    resume_drafts: Mapped[list["ResumeDraft"]] = relationship(
        back_populates="job_analysis", cascade="all, delete-orphan"
    )
    generated_documents: Mapped[list["GeneratedDocument"]] = relationship(
        back_populates="job_analysis", cascade="all, delete-orphan"
    )
    application_records: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="job_analysis"
    )
