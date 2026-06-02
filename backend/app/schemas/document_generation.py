"""Pydantic contracts for local resume-document generation."""

from pathlib import Path
from uuid import UUID

from pydantic import Field

from app.models.enums import (
    DocumentFormat,
    DocumentGenerationStatus,
    ResumeTemplateName,
)
from app.schemas.knowledge_base import EntityRead, ReadSchema, SchemaBase


class GeneratedDocumentCreate(SchemaBase):
    """Create metadata for one local document-generation attempt."""

    resume_draft_id: UUID
    candidate_profile_id: UUID
    job_analysis_id: UUID
    template_name: ResumeTemplateName | str
    output_format: DocumentFormat | str
    file_name: str = Field(min_length=1, max_length=500)
    file_path: str = Field(min_length=1, max_length=2000)
    file_size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = Field(default=None, min_length=64, max_length=64)
    generation_status: DocumentGenerationStatus | str = DocumentGenerationStatus.PENDING
    error_message: str | None = None


class GeneratedDocumentRead(EntityRead, GeneratedDocumentCreate):
    """Read persisted metadata for a generated resume file."""


class DocumentGenerationRequest(SchemaBase):
    """Request one local resume export from an approved structured draft."""

    resume_draft_id: UUID
    template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS
    output_format: DocumentFormat = DocumentFormat.MARKDOWN
    output_directory: Path | None = None


class DocumentGenerationResult(ReadSchema):
    """Return generated-file metadata to API consumers."""

    document: GeneratedDocumentRead
