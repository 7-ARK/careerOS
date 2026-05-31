"""Pydantic contracts for job-description capture and structured analysis."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import AnyHttpUrl, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.models.enums import EmploymentType, SourcePlatform, WorkplaceType
from app.schemas.knowledge_base import EntityRead, ReadSchema, SchemaBase

HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _normalize_label(value: str | None) -> str | None:
    """Normalize optional integration metadata while preserving custom values."""
    return value.strip().lower().replace("-", "_").replace(" ", "_") if value else None


class JobDescriptionBase(SchemaBase):
    """Shared fields for a captured job posting."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    raw_title: str = Field(min_length=1, max_length=250)
    company_name: str | None = Field(default=None, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: SourcePlatform | str | None = Field(default=None, max_length=100)
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str = Field(min_length=1)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    employment_type: EmploymentType | str | None = Field(default=None, max_length=100)
    workplace_type: WorkplaceType | str | None = Field(default=None, max_length=100)
    posted_at: datetime | None = None

    @field_validator("source_platform", "employment_type", "workplace_type", mode="before")
    @classmethod
    def normalize_metadata_label(cls, value: str | None) -> str | None:
        """Normalize canonical and custom metadata values for stable filtering."""
        return _normalize_label(value)

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str | None) -> str | None:
        """Require a valid HTTP URL when a source link is provided."""
        return str(HTTP_URL_ADAPTER.validate_python(value)) if value else None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
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

    raw_title: str | None = Field(default=None, min_length=1, max_length=250)
    company_name: str | None = Field(default=None, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: SourcePlatform | str | None = Field(default=None, max_length=100)
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str | None = Field(default=None, min_length=1)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    employment_type: EmploymentType | str | None = Field(default=None, max_length=100)
    workplace_type: WorkplaceType | str | None = Field(default=None, max_length=100)
    posted_at: datetime | None = None

    @field_validator("source_platform", "employment_type", "workplace_type", mode="before")
    @classmethod
    def normalize_metadata_label(cls, value: str | None) -> str | None:
        """Normalize canonical and custom metadata values for stable filtering."""
        return _normalize_label(value)

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str | None) -> str | None:
        """Require a valid HTTP URL when a source link is provided."""
        return str(HTTP_URL_ADAPTER.validate_python(value)) if value else None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """Normalize ISO-like salary currency codes."""
        return value.upper() if value else None


class JobDescriptionRead(EntityRead, JobDescriptionBase):
    """Read a captured job-description source record."""


class JobDescriptionInput(ReadSchema):
    """Provider-facing snapshot of a captured source posting."""

    id: UUID | None = None
    raw_title: str
    company_name: str | None = None
    location: str | None = None
    source_platform: str | None = None
    job_url: str | None = None
    description_text: str
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    currency: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    posted_at: datetime | None = None


class JobAnalysisResult(SchemaBase):
    """Provider-independent structured intelligence for downstream matching."""

    normalized_title: str = Field(min_length=1, max_length=250)
    seniority_level: str = Field(min_length=1, max_length=100)
    estimated_years_min: int | None = Field(default=None, ge=0)
    estimated_years_max: int | None = Field(default=None, ge=0)
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
    job_summary: str = Field(min_length=1)
    match_relevant_signals: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_experience_range(self) -> Self:
        """Ensure inferred experience bounds are coherent."""
        if self.estimated_years_min is not None and self.estimated_years_max is not None:
            if self.estimated_years_max < self.estimated_years_min:
                raise ValueError("estimated_years_max must not be lower than estimated_years_min")
        return self


class JobAnalysisCreate(JobAnalysisResult):
    """Create a persisted analysis revision."""

    job_description_id: UUID
    revision: int = Field(ge=1)
    analyzer_name: str = Field(min_length=1, max_length=100)
    analyzer_version: str = Field(min_length=1, max_length=50)


class JobAnalysisUpdate(SchemaBase):
    """Update metadata or output fields on an analysis revision."""

    normalized_title: str | None = Field(default=None, min_length=1, max_length=250)
    seniority_level: str | None = Field(default=None, min_length=1, max_length=100)
    estimated_years_min: int | None = Field(default=None, ge=0)
    estimated_years_max: int | None = Field(default=None, ge=0)
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


# Transitional aliases for callers using the original v1 draft names.
JobDescriptionAnalysisInput = JobDescriptionInput
JobAnalysisPayload = JobAnalysisResult
