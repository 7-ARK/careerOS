"""Pydantic schemas for candidate knowledge-base commands and responses."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ApplicationStatus,
    RelocationPreference,
    RemotePreference,
    ResumeStyle,
)


class SchemaBase(BaseModel):
    """Reject unknown input fields at application boundaries."""

    model_config = ConfigDict(extra="forbid")


class ReadSchema(SchemaBase):
    """Enable schema construction from SQLAlchemy entities."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class EntityRead(ReadSchema):
    """Fields shared by persisted knowledge-base entities."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class OptionalDateRange(SchemaBase):
    """Validate chronological records with optional start and end dates."""

    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Ensure an optional end date does not precede the start date."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        return self


class CandidateProfileCreate(SchemaBase):
    """Create a candidate's durable professional profile."""

    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    headline: str | None = Field(default=None, max_length=250)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=200)
    linkedin_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)


class CandidateProfileUpdate(SchemaBase):
    """Update mutable profile fields."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    headline: str | None = Field(default=None, max_length=250)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=200)
    linkedin_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)


class EducationBase(OptionalDateRange):
    """Shared education fields."""

    institution: str = Field(min_length=1, max_length=250)
    degree: str = Field(min_length=1, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    description: str | None = None


class EducationCreate(EducationBase):
    """Create an education record."""


class EducationUpdate(OptionalDateRange):
    """Update an education record."""

    institution: str | None = Field(default=None, min_length=1, max_length=250)
    degree: str | None = Field(default=None, min_length=1, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    description: str | None = None


class EducationRead(EntityRead, EducationBase):
    """Read an education record."""

    profile_id: UUID


class WorkExperienceCreate(OptionalDateRange):
    """Create a work experience record."""

    company: str = Field(min_length=1, max_length=250)
    job_title: str = Field(min_length=1, max_length=250)
    employment_type: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    start_date: date
    is_current: bool = False
    description: str | None = None
    achievements: list[str] = Field(default_factory=list)


class WorkExperienceUpdate(OptionalDateRange):
    """Update a work experience record."""

    company: str | None = Field(default=None, min_length=1, max_length=250)
    job_title: str | None = Field(default=None, min_length=1, max_length=250)
    employment_type: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    is_current: bool | None = None
    description: str | None = None
    achievements: list[str] | None = None


class WorkExperienceRead(EntityRead):
    """Read a work experience record."""

    profile_id: UUID
    company: str
    job_title: str
    employment_type: str | None
    location: str | None
    start_date: date
    end_date: date | None
    is_current: bool
    description: str | None
    achievements: list[str]


class ProjectCreate(OptionalDateRange):
    """Create a project record."""

    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1)
    technologies: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)


class ProjectUpdate(OptionalDateRange):
    """Update a project record."""

    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, min_length=1)
    technologies: list[str] | None = None
    outcomes: list[str] | None = None
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)


class ProjectRead(EntityRead):
    """Read a project record."""

    profile_id: UUID
    title: str
    description: str
    technologies: list[str]
    outcomes: list[str]
    github_url: str | None
    portfolio_url: str | None
    start_date: date | None
    end_date: date | None


class SkillCreate(SchemaBase):
    """Create a candidate skill."""

    name: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    self_rating: int = Field(ge=1, le=5)
    years_of_experience: Decimal = Field(ge=0, max_digits=5, decimal_places=2)


class SkillUpdate(SchemaBase):
    """Update a candidate skill."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    self_rating: int | None = Field(default=None, ge=1, le=5)
    years_of_experience: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=2)


class SkillRead(EntityRead):
    """Read a candidate skill."""

    profile_id: UUID
    name: str
    category: str
    self_rating: int
    years_of_experience: Decimal


class CertificationCreate(SchemaBase):
    """Create a certification record."""

    name: str = Field(min_length=1, max_length=250)
    issuing_organization: str = Field(min_length=1, max_length=250)
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=250)
    credential_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Ensure certification expiration follows issuance."""
        if self.issue_date and self.expiration_date and self.expiration_date < self.issue_date:
            raise ValueError("expiration_date must not be earlier than issue_date")
        return self


class CertificationUpdate(SchemaBase):
    """Update a certification record."""

    name: str | None = Field(default=None, min_length=1, max_length=250)
    issuing_organization: str | None = Field(default=None, min_length=1, max_length=250)
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=250)
    credential_url: str | None = Field(default=None, max_length=500)


class CertificationRead(EntityRead):
    """Read a certification record."""

    profile_id: UUID
    name: str
    issuing_organization: str
    issue_date: date | None
    expiration_date: date | None
    credential_id: str | None
    credential_url: str | None


class CareerGoalCreate(SchemaBase):
    """Create candidate career goals and opportunity matching constraints."""

    target_roles: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_currency: str = Field(default="USD", min_length=3, max_length=3)
    remote_preference: RemotePreference = RemotePreference.FLEXIBLE
    relocation_preference: RelocationPreference = RelocationPreference.CONDITIONAL
    geographic_preferences: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_salary_range(self) -> Self:
        """Ensure the salary range is coherent."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_max < self.salary_min:
                raise ValueError("salary_max must not be lower than salary_min")
        return self


class CareerGoalUpdate(SchemaBase):
    """Update candidate career goals."""

    target_roles: list[str] | None = None
    preferred_industries: list[str] | None = None
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    remote_preference: RemotePreference | None = None
    relocation_preference: RelocationPreference | None = None
    geographic_preferences: list[str] | None = None


class CareerGoalRead(EntityRead):
    """Read candidate career goals."""

    profile_id: UUID
    target_roles: list[str]
    preferred_industries: list[str]
    salary_min: Decimal | None
    salary_max: Decimal | None
    salary_currency: str
    remote_preference: RemotePreference
    relocation_preference: RelocationPreference
    geographic_preferences: list[str]


class PreferenceCreate(SchemaBase):
    """Create candidate output and communication preferences."""

    resume_style: ResumeStyle = ResumeStyle.ATS_FOCUSED
    resume_preferences: dict[str, Any] = Field(default_factory=dict)
    application_preferences: dict[str, Any] = Field(default_factory=dict)
    communication_preferences: dict[str, Any] = Field(default_factory=dict)


class PreferenceUpdate(SchemaBase):
    """Update candidate output and communication preferences."""

    resume_style: ResumeStyle | None = None
    resume_preferences: dict[str, Any] | None = None
    application_preferences: dict[str, Any] | None = None
    communication_preferences: dict[str, Any] | None = None


class PreferenceRead(EntityRead):
    """Read candidate output and communication preferences."""

    profile_id: UUID
    resume_style: ResumeStyle
    resume_preferences: dict[str, Any]
    application_preferences: dict[str, Any]
    communication_preferences: dict[str, Any]


class ResumeVersionCreate(SchemaBase):
    """Create a resume artifact derived from the knowledge base."""

    title: str = Field(min_length=1, max_length=250)
    version_label: str | None = Field(default=None, max_length=100)
    content: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    is_primary: bool = False
    source_profile_updated_at: datetime | None = None


class ResumeVersionUpdate(SchemaBase):
    """Update a derived resume artifact."""

    title: str | None = Field(default=None, min_length=1, max_length=250)
    version_label: str | None = Field(default=None, max_length=100)
    content: dict[str, Any] | None = None
    notes: str | None = None
    is_primary: bool | None = None
    source_profile_updated_at: datetime | None = None


class ResumeVersionRead(EntityRead):
    """Read a historical resume artifact."""

    profile_id: UUID
    title: str
    version_label: str | None
    content: dict[str, Any]
    notes: str | None
    is_primary: bool
    source_profile_updated_at: datetime | None


class ApplicationHistoryCreate(SchemaBase):
    """Record a job application."""

    resume_version_id: UUID | None = None
    job_description_id: UUID | None = None
    company: str = Field(min_length=1, max_length=250)
    job_title: str = Field(min_length=1, max_length=250)
    job_url: str | None = Field(default=None, max_length=500)
    application_date: date
    status: ApplicationStatus = ApplicationStatus.APPLIED
    notes: str | None = None


class ApplicationHistoryUpdate(SchemaBase):
    """Update a recorded job application."""

    resume_version_id: UUID | None = None
    job_description_id: UUID | None = None
    company: str | None = Field(default=None, min_length=1, max_length=250)
    job_title: str | None = Field(default=None, min_length=1, max_length=250)
    job_url: str | None = Field(default=None, max_length=500)
    application_date: date | None = None
    status: ApplicationStatus | None = None
    notes: str | None = None


class ApplicationHistoryRead(EntityRead):
    """Read a job application lifecycle record."""

    profile_id: UUID
    resume_version_id: UUID | None
    job_description_id: UUID | None
    company: str
    job_title: str
    job_url: str | None
    application_date: date
    status: ApplicationStatus
    notes: str | None


class CandidateProfileRead(EntityRead):
    """Read the complete candidate knowledge-base aggregate."""

    full_name: str
    email: str | None
    phone: str | None
    headline: str | None
    summary: str | None
    location: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    education: list[EducationRead] = Field(default_factory=list)
    work_experiences: list[WorkExperienceRead] = Field(default_factory=list)
    projects: list[ProjectRead] = Field(default_factory=list)
    skills: list[SkillRead] = Field(default_factory=list)
    certifications: list[CertificationRead] = Field(default_factory=list)
    career_goals: CareerGoalRead | None = None
    preferences: PreferenceRead | None = None
    resume_versions: list[ResumeVersionRead] = Field(default_factory=list)
    applications: list[ApplicationHistoryRead] = Field(default_factory=list)
