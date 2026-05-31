"""Pydantic contracts for job-description capture and structured analysis."""

from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.models.enums import JobWorkplaceType, SeniorityLevel
from app.schemas.knowledge_base import EntityRead, ReadSchema, SchemaBase


class JobDescriptionBase(SchemaBase):
    """Shared fields for a captured job posting."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    raw_job_title: str = Field(min_length=1, max_length=250)
    company_name: str = Field(min_length=1, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: str | None = Field(default=None, max_length=100)
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str = Field(min_length=1)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    employment_type: str | None = Field(default=None, max_length=100)
    workplace_type: JobWorkplaceType | None = None

    @field_validator("salary_currency")
    @classmethod
    def normalize_salary_currency(cls, value: str | None) -> str | None:
        """Normalize ISO-like salary currency codes."""
        return value.upper() if value else None

    @model_validator(mode="after")
    def validate_salary_range(self) -> Self:
        """Ensure salary bounds are coherent."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_max < self.salary_min:
                raise ValueError("salary_max must not be lower than salary_min")
        return self


class JobDescriptionCreate(JobDescriptionBase):
    """Create a captured job-description source record."""


class JobDescriptionUpdate(SchemaBase):
    """Update fields on a captured job-description source record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    raw_job_title: str | None = Field(default=None, min_length=1, max_length=250)
    company_name: str | None = Field(default=None, min_length=1, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: str | None = Field(default=None, max_length=100)
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str | None = Field(default=None, min_length=1)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    employment_type: str | None = Field(default=None, max_length=100)
    workplace_type: JobWorkplaceType | None = None

    @field_validator("salary_currency")
    @classmethod
    def normalize_salary_currency(cls, value: str | None) -> str | None:
        """Normalize ISO-like salary currency codes."""
        return value.upper() if value else None


class JobDescriptionRead(EntityRead, JobDescriptionBase):
    """Read a captured job-description source record."""


class JobDescriptionAnalysisInput(ReadSchema):
    """Provider-facing snapshot of the source job posting."""

    id: UUID | None = None
    raw_job_title: str
    company_name: str
    location: str | None = None
    source_platform: str | None = None
    job_url: str | None = None
    description_text: str
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    employment_type: str | None = None
    workplace_type: JobWorkplaceType | None = None


class JobAnalysisPayload(SchemaBase):
    """Structured intelligence emitted by a job analyzer provider."""

    normalized_job_title: str = Field(min_length=1, max_length=250)
    seniority_level: SeniorityLevel
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    preferred_technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    domain_keywords: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    estimated_experience_level: str | None = Field(default=None, max_length=100)
    job_summary: str = Field(min_length=1)
    match_relevant_signals: dict[str, Any] = Field(default_factory=dict)


class JobAnalysisCreate(JobAnalysisPayload):
    """Create a persisted analysis revision."""

    job_description_id: UUID
    revision: int = Field(ge=1)
    analyzer_name: str = Field(min_length=1, max_length=100)
    analyzer_version: str = Field(min_length=1, max_length=50)


class JobAnalysisUpdate(SchemaBase):
    """Update metadata or output fields on an analysis revision."""

    normalized_job_title: str | None = Field(default=None, min_length=1, max_length=250)
    seniority_level: SeniorityLevel | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    required_technologies: list[str] | None = None
    preferred_technologies: list[str] | None = None
    responsibilities: list[str] | None = None
    qualifications: list[str] | None = None
    soft_skills: list[str] | None = None
    domain_keywords: list[str] | None = None
    ats_keywords: list[str] | None = None
    red_flags: list[str] | None = None
    missing_information: list[str] | None = None
    estimated_experience_level: str | None = Field(default=None, max_length=100)
    job_summary: str | None = Field(default=None, min_length=1)
    match_relevant_signals: dict[str, Any] | None = None


class JobAnalysisRead(EntityRead, JobAnalysisCreate):
    """Read a persisted job-analysis revision."""


class AnalyzedJobRead(ReadSchema):
    """API-ready view of a source posting with its latest analysis."""

    job_description: JobDescriptionRead
    analysis: JobAnalysisRead


class JobAnalysisListFilters(SchemaBase):
    """Search and filtering criteria for analyzed job listings."""

    keyword: str | None = Field(default=None, min_length=1, max_length=250)
    title: str | None = Field(default=None, min_length=1, max_length=250)
    company: str | None = Field(default=None, min_length=1, max_length=250)
    platform: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=250)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
