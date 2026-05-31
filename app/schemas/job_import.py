"""Pydantic contracts for manually imported job postings."""

from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    ConfigDict,
    EmailStr,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.models.enums import EmploymentType, SourcePlatform, WorkplaceType
from app.schemas.application_tracking import ApplicationRecordRead
from app.schemas.job_analysis import JobAnalysisRead, JobDescriptionRead
from app.schemas.knowledge_base import ReadSchema, SchemaBase

HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class ManualJobImportRequest(SchemaBase):
    """Capture manually pasted job-posting data for deterministic analysis."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    candidate_profile_id: UUID
    raw_title: str = Field(min_length=1, max_length=250)
    company_name: str = Field(min_length=1, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    source_platform: SourcePlatform = SourcePlatform.UNKNOWN
    job_url: str | None = Field(default=None, max_length=1000)
    description_text: str = Field(min_length=1)
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    employment_type: EmploymentType | str | None = Field(default=None, max_length=100)
    workplace_type: WorkplaceType | str | None = Field(default=None, max_length=100)
    create_application_record: bool = True
    company_email: EmailStr | None = None

    @field_validator("source_platform", mode="before")
    @classmethod
    def normalize_source_platform(cls, value: object) -> object:
        """Accept human-entered platform labels while storing canonical values."""
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_").replace(" ", "_")
        return value

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str | None) -> str | None:
        """Require a valid HTTP URL when a manually pasted link is provided."""
        return str(HTTP_URL_ADAPTER.validate_python(value)) if value else None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """Normalize ISO-like salary currency codes."""
        return value.upper() if value else None

    @model_validator(mode="after")
    def validate_salary_range(self) -> Self:
        """Ensure manually entered salary bounds are coherent."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_max < self.salary_min:
                raise ValueError("salary_max must not be lower than salary_min")
        return self


class ManualJobImportResult(ReadSchema):
    """Return all records created by one manual import workflow."""

    job_description: JobDescriptionRead
    analysis: JobAnalysisRead
    application_record: ApplicationRecordRead | None = None
