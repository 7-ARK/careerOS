"""Pydantic contracts for the lightweight application tracker."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field, StringConstraints, field_validator

from app.models.enums import ApplicationStatus
from app.schemas.knowledge_base import EntityRead, SchemaBase

TrackerApplicationStatus = Literal[
    ApplicationStatus.NOT_APPLIED,
    ApplicationStatus.SAVED,
    ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEWING,
    ApplicationStatus.OFFER,
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.ARCHIVED,
]
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApplicationRecordCreate(SchemaBase):
    """Create a lightweight candidate application record."""

    candidate_profile_id: UUID
    job_description_id: UUID | None = None
    job_analysis_id: UUID | None = None
    generated_document_id: UUID | None = None
    company_name: RequiredText = Field(max_length=250)
    role_title: RequiredText = Field(max_length=250)
    company_email: EmailStr | None = None
    job_url: str | None = Field(default=None, max_length=1000)
    status: TrackerApplicationStatus = ApplicationStatus.NOT_APPLIED
    notes: str | None = None
    evidence_coverage_score: Decimal | None = Field(default=None, ge=0, le=100)
    applied_at: datetime | None = None

    @field_validator("job_url", "notes", mode="before")
    @classmethod
    def empty_strings_to_none(cls, value: object) -> object:
        """Treat optional empty text values as absent."""
        return None if isinstance(value, str) and not value.strip() else value


class ApplicationRecordUpdate(SchemaBase):
    """Update editable fields on a lightweight application record."""

    job_description_id: UUID | None = None
    job_analysis_id: UUID | None = None
    generated_document_id: UUID | None = None
    company_name: RequiredText | None = Field(default=None, max_length=250)
    role_title: RequiredText | None = Field(default=None, max_length=250)
    company_email: EmailStr | None = None
    job_url: str | None = Field(default=None, max_length=1000)
    status: TrackerApplicationStatus | None = None
    notes: str | None = None
    evidence_coverage_score: Decimal | None = Field(default=None, ge=0, le=100)

    @field_validator("job_url", "notes", mode="before")
    @classmethod
    def empty_strings_to_none(cls, value: object) -> object:
        """Treat optional empty text values as absent."""
        return None if isinstance(value, str) and not value.strip() else value


class ApplicationRecordRead(EntityRead):
    """Read one lightweight application record."""

    candidate_profile_id: UUID
    job_description_id: UUID | None
    job_analysis_id: UUID | None
    generated_document_id: UUID | None
    company_name: str
    role_title: str
    company_email: EmailStr | None
    job_url: str | None
    status: TrackerApplicationStatus
    notes: str | None
    evidence_coverage_score: Decimal | None = None
    applied_at: datetime | None

    @field_validator("applied_at", mode="before")
    @classmethod
    def normalize_applied_at_timezone(cls, value: object) -> object:
        """Normalize SQLite's naive test timestamps to the UTC API contract."""
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ApplicationStatusUpdate(SchemaBase):
    """Update only the user-facing application lifecycle state."""

    status: TrackerApplicationStatus
