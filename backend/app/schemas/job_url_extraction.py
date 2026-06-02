"""Pydantic contracts for user-authorized single-URL job extraction."""

from decimal import Decimal
from uuid import UUID

from pydantic import AnyHttpUrl, EmailStr, Field, TypeAdapter, field_validator

from app.models.enums import (
    DocumentFormat,
    ResumeTemplateName,
    SourcePlatform,
)
from app.schemas.knowledge_base import ReadSchema, SchemaBase
from app.schemas.pipeline import ManualJobPipelineResult

HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class JobUrlExtractionRequest(SchemaBase):
    """Request one user-authorized Playwright extraction."""

    candidate_profile_id: UUID
    job_url: str = Field(min_length=1, max_length=1000)
    source_platform: SourcePlatform | None = None
    create_application_record: bool = True
    resume_template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS
    document_format: DocumentFormat = DocumentFormat.PDF
    company_email: EmailStr | None = None
    headless: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=120)

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str) -> str:
        """Require a valid HTTP URL for browser navigation."""
        return str(HTTP_URL_ADAPTER.validate_python(value))

    @field_validator("source_platform", mode="before")
    @classmethod
    def normalize_source_platform(cls, value: object) -> object:
        """Accept human-entered canonical platform labels."""
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_").replace(" ", "_")
        return value


class JobUrlExtractionResult(ReadSchema):
    """Return safely extracted visible job-posting data."""

    job_url: str
    detected_platform: SourcePlatform
    raw_title: str | None = None
    company_name: str | None = None
    location: str | None = None
    description_text: str
    employment_type: str | None = None
    workplace_type: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    currency: str | None = None
    extraction_confidence: Decimal = Field(ge=0, le=1)
    extraction_warnings: list[str] = Field(default_factory=list)
    pipeline_ready: bool


class JobUrlPipelineRequest(JobUrlExtractionRequest):
    """Extract one URL and optionally run the existing application pipeline."""


class JobUrlPipelineResult(ReadSchema):
    """Return extraction output and an optional downstream pipeline result."""

    extraction: JobUrlExtractionResult
    pipeline: ManualJobPipelineResult | None = None
