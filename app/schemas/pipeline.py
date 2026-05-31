"""Pydantic contracts for the end-to-end manual application pipeline."""

from decimal import Decimal
from uuid import UUID

from app.models.enums import (
    DocumentFormat,
    PipelineStatus,
    ResumeTemplateName,
)
from app.schemas.job_import import ManualJobImportRequest
from app.schemas.knowledge_base import ReadSchema


class ManualJobPipelineRequest(ManualJobImportRequest):
    """Run the complete local pipeline from pasted job data to resume export."""

    resume_template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS
    document_format: DocumentFormat = DocumentFormat.PDF


class ManualJobPipelineResult(ReadSchema):
    """Return the identifiers and review signals created by one pipeline run."""

    job_description_id: UUID
    job_analysis_id: UUID
    resume_analysis_id: UUID
    resume_draft_id: UUID
    generated_document_id: UUID
    generated_file_path: str
    application_record_id: UUID | None = None
    company_name: str
    role_title: str
    match_score: Decimal
    document_format: DocumentFormat
    template_name: ResumeTemplateName
    status: PipelineStatus
    warnings: list[str]
    next_actions: list[str]
