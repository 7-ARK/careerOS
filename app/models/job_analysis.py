"""Persistence models for captured job descriptions and derived intelligence."""

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import JobWorkplaceType, SeniorityLevel

if TYPE_CHECKING:
    from app.models.knowledge_base import ApplicationHistory


class JobDescription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Captured source job posting before analysis."""

    __tablename__ = "job_descriptions"
    __table_args__ = (
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
        Index("ix_job_descriptions_company_title", "company_name", "raw_job_title"),
        Index("ix_job_descriptions_platform_location", "source_platform", "location"),
    )

    raw_job_title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(250), index=True)
    source_platform: Mapped[str | None] = mapped_column(String(100), index=True)
    job_url: Mapped[str | None] = mapped_column(String(1000))
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    employment_type: Mapped[str | None] = mapped_column(String(100), index=True)
    workplace_type: Mapped[JobWorkplaceType | None] = mapped_column(
        Enum(JobWorkplaceType, native_enum=False), index=True
    )

    analyses: Mapped[list["JobAnalysis"]] = relationship(
        back_populates="job_description",
        cascade="all, delete-orphan",
        order_by="JobAnalysis.revision",
    )
    applications: Mapped[list["ApplicationHistory"]] = relationship(
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
        Index("ix_job_analyses_title_seniority", "normalized_job_title", "seniority_level"),
    )

    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(nullable=False)
    analyzer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_job_title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    seniority_level: Mapped[SeniorityLevel] = mapped_column(
        Enum(SeniorityLevel, native_enum=False), nullable=False, index=True
    )
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
    estimated_experience_level: Mapped[str | None] = mapped_column(String(100))
    job_summary: Mapped[str] = mapped_column(Text, nullable=False)
    match_relevant_signals: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    job_description: Mapped[JobDescription] = relationship(back_populates="analyses")
