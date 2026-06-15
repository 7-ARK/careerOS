"""Relational source-of-truth models for the candidate knowledge base."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ApplicationStatus,
    RelocationPreference,
    RemotePreference,
    ResumeStyle,
)

if TYPE_CHECKING:
    from app.models.application_tracking import ApplicationRecord
    from app.models.auth import User
    from app.models.document_generation import GeneratedDocument
    from app.models.job_analysis import JobDescription
    from app.models.resume_intelligence import ResumeAnalysis, ResumeDraft


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Aggregate root containing a candidate's durable professional identity."""

    __tablename__ = "candidate_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    headline: Mapped[str | None] = mapped_column(String(250))
    summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200), index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="candidate_profiles")

    education: Mapped[list["Education"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    work_experiences: Mapped[list["WorkExperience"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    career_goals: Mapped["CareerGoal | None"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False
    )
    preferences: Mapped["Preference | None"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False
    )
    resume_versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    applications: Mapped[list["ApplicationHistory"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    resume_analyses: Mapped[list["ResumeAnalysis"]] = relationship(
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    resume_drafts: Mapped[list["ResumeDraft"]] = relationship(
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    generated_documents: Mapped[list["GeneratedDocument"]] = relationship(
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    application_records: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )


class Education(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate education record."""

    __tablename__ = "education"
    __table_args__ = (
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="date_range",
        ),
        Index("ix_education_profile_institution", "profile_id", "institution"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution: Mapped[str] = mapped_column(String(250), nullable=False)
    degree: Mapped[str] = mapped_column(String(200), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[CandidateProfile] = relationship(back_populates="education")


class WorkExperience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate employment history record."""

    __tablename__ = "work_experiences"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR start_date <= end_date", name="date_range"),
        Index("ix_work_experiences_profile_company", "profile_id", "company"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(250), nullable=False)
    job_title: Mapped[str] = mapped_column(String(250), nullable=False)
    employment_type: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    profile: Mapped[CandidateProfile] = relationship(back_populates="work_experiences")


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate project with evidence and measurable outcomes."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="date_range",
        ),
        Index("ix_projects_profile_title", "profile_id", "title"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    outcomes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    profile: Mapped[CandidateProfile] = relationship(back_populates="projects")


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate skill with category, confidence, and experience duration."""

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "name"),
        CheckConstraint("self_rating >= 1 AND self_rating <= 5", name="self_rating_range"),
        CheckConstraint("years_of_experience >= 0", name="years_of_experience_non_negative"),
        Index("ix_skills_profile_category", "profile_id", "category"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    self_rating: Mapped[int] = mapped_column(nullable=False)
    years_of_experience: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    profile: Mapped[CandidateProfile] = relationship(back_populates="skills")


class Certification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Professional certification or credential."""

    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint(
            "issue_date IS NULL OR expiration_date IS NULL OR issue_date <= expiration_date",
            name="date_range",
        ),
        Index("ix_certifications_profile_name", "profile_id", "name"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    issuing_organization: Mapped[str] = mapped_column(String(250), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    credential_id: Mapped[str | None] = mapped_column(String(250))
    credential_url: Mapped[str | None] = mapped_column(String(500))

    profile: Mapped[CandidateProfile] = relationship(back_populates="certifications")


class CareerGoal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate career direction and opportunity matching constraints."""

    __tablename__ = "career_goals"
    __table_args__ = (
        UniqueConstraint("profile_id"),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_industries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    remote_preference: Mapped[RemotePreference] = mapped_column(
        Enum(RemotePreference, native_enum=False), nullable=False, default=RemotePreference.FLEXIBLE
    )
    relocation_preference: Mapped[RelocationPreference] = mapped_column(
        Enum(RelocationPreference, native_enum=False),
        nullable=False,
        default=RelocationPreference.CONDITIONAL,
    )
    geographic_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    profile: Mapped[CandidateProfile] = relationship(back_populates="career_goals")


class Preference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate preferences for generated artifacts and communication."""

    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("profile_id"),)

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_style: Mapped[ResumeStyle] = mapped_column(
        Enum(ResumeStyle, native_enum=False), nullable=False, default=ResumeStyle.ATS_FOCUSED
    )
    resume_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    application_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    communication_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    profile: Mapped[CandidateProfile] = relationship(back_populates="preferences")


class ResumeVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Historical resume artifact derived from the candidate knowledge base."""

    __tablename__ = "resume_versions"
    __table_args__ = (Index("ix_resume_versions_profile_created", "profile_id", "created_at"),)

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100))
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_profile_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[CandidateProfile] = relationship(back_populates="resume_versions")
    applications: Mapped[list["ApplicationHistory"]] = relationship(back_populates="resume_version")


class ApplicationHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Job application lifecycle record."""

    __tablename__ = "application_history"
    __table_args__ = (
        Index("ix_application_history_profile_status", "profile_id", "status"),
        Index("ix_application_history_profile_company", "profile_id", "company"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), index=True
    )
    job_description_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="SET NULL"), index=True
    )
    company: Mapped[str] = mapped_column(String(250), nullable=False)
    job_title: Mapped[str] = mapped_column(String(250), nullable=False)
    job_url: Mapped[str | None] = mapped_column(String(500))
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False),
        nullable=False,
        default=ApplicationStatus.APPLIED,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[CandidateProfile] = relationship(back_populates="applications")
    resume_version: Mapped[ResumeVersion | None] = relationship(back_populates="applications")
    job_description: Mapped["JobDescription | None"] = relationship(back_populates="applications")
