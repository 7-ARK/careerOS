"""Transactional local document-generation orchestration."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.features.document_generation.exporters import (
    DocumentExporter,
    DocxExporter,
    MarkdownExporter,
    PdfExporter,
)
from app.features.document_generation.templates import get_resume_template
from app.models import CandidateProfile, GeneratedDocument, ResumeDraft
from app.models.enums import (
    DocumentFormat,
    DocumentGenerationStatus,
    ResumeDraftStatus,
    ResumeTemplateName,
)
from app.repositories import GeneratedDocumentRepository, ResumeDraftRepository
from app.schemas import (
    DocumentGenerationRequest,
    DocumentGenerationResult,
    GeneratedDocumentCreate,
    GeneratedDocumentRead,
)
from app.services.exceptions import (
    DocumentGenerationError,
    GeneratedDocumentNotFoundError,
    ProfileNotFoundError,
    ResumeDraftNotApprovedError,
    ResumeDraftNotFoundError,
    UnsupportedDocumentFormatError,
)

DEFAULT_OUTPUT_DIRECTORY = Path("generated/resumes")


class DocumentGenerationService:
    """Generate local resume files from approved structured drafts."""

    def __init__(
        self,
        session: Session,
        *,
        output_directory: Path | None = None,
        exporters: Mapping[DocumentFormat, DocumentExporter] | None = None,
    ) -> None:
        """Build an injectable local document-generation service."""
        self.session = session
        self.documents = GeneratedDocumentRepository(session)
        self.drafts = ResumeDraftRepository(session)
        self.output_directory = output_directory or DEFAULT_OUTPUT_DIRECTORY
        self.exporters = (
            dict(exporters)
            if exporters is not None
            else {
                DocumentFormat.MARKDOWN: MarkdownExporter(),
                DocumentFormat.DOCX: DocxExporter(),
                DocumentFormat.PDF: PdfExporter(),
            }
        )

    def generate_from_resume_draft(
        self, request: DocumentGenerationRequest
    ) -> DocumentGenerationResult:
        """Generate one requested format and persist immutable file metadata."""
        draft = self._require_approved_draft(request.resume_draft_id)
        candidate = self._require_candidate(draft.candidate_profile_id)
        exporter = self._require_exporter(request.output_format)
        template = get_resume_template(request.template_name)
        output_directory = (request.output_directory or self.output_directory).resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        document_id = uuid4()
        file_name = self._file_name(candidate, draft, request.template_name, exporter, document_id)
        output_path = output_directory / file_name
        document = self.documents.create_generated_document(
            **GeneratedDocumentCreate(
                resume_draft_id=draft.id,
                candidate_profile_id=draft.candidate_profile_id,
                job_analysis_id=draft.job_analysis_id,
                template_name=request.template_name,
                output_format=request.output_format,
                file_name=file_name,
                file_path=str(output_path),
            ).model_dump(),
            id=document_id,
        )
        try:
            exporter.export(template.render(draft, candidate), output_path)
            self.documents.update(
                document,
                {
                    "file_size_bytes": output_path.stat().st_size,
                    "checksum": self.calculate_checksum(output_path),
                    "generation_status": str(DocumentGenerationStatus.COMPLETED),
                },
            )
            self._commit()
        except Exception as exc:
            self._record_failure(document, output_path, exc)
            raise DocumentGenerationError(
                f"failed to generate {request.output_format} resume"
            ) from exc
        return DocumentGenerationResult(document=GeneratedDocumentRead.model_validate(document))

    def generate_markdown(
        self,
        resume_draft_id: UUID,
        *,
        template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS,
        output_directory: Path | None = None,
    ) -> DocumentGenerationResult:
        """Generate a local Markdown resume."""
        return self._generate(
            resume_draft_id, template_name, DocumentFormat.MARKDOWN, output_directory
        )

    def generate_docx(
        self,
        resume_draft_id: UUID,
        *,
        template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS,
        output_directory: Path | None = None,
    ) -> DocumentGenerationResult:
        """Generate a local editable DOCX resume."""
        return self._generate(resume_draft_id, template_name, DocumentFormat.DOCX, output_directory)

    def generate_pdf(
        self,
        resume_draft_id: UUID,
        *,
        template_name: ResumeTemplateName = ResumeTemplateName.CLEAN_ATS,
        output_directory: Path | None = None,
    ) -> DocumentGenerationResult:
        """Generate a local selectable-text PDF resume."""
        return self._generate(resume_draft_id, template_name, DocumentFormat.PDF, output_directory)

    def get_generated_document(self, generated_document_id: UUID) -> GeneratedDocumentRead:
        """Return persisted metadata for one local generated file."""
        document = self.documents.get(generated_document_id)
        if document is None:
            raise GeneratedDocumentNotFoundError(
                f"generated document {generated_document_id} was not found"
            )
        return GeneratedDocumentRead.model_validate(document)

    def list_documents_by_candidate(
        self, candidate_profile_id: UUID
    ) -> list[GeneratedDocumentRead]:
        """List generated-file metadata for one candidate."""
        return [
            GeneratedDocumentRead.model_validate(document)
            for document in self.documents.list_by_candidate(candidate_profile_id)
        ]

    def list_documents_by_draft(self, resume_draft_id: UUID) -> list[GeneratedDocumentRead]:
        """List generated-file metadata for one structured draft."""
        return [
            GeneratedDocumentRead.model_validate(document)
            for document in self.documents.list_by_draft(resume_draft_id)
        ]

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """Return the SHA-256 checksum for a generated local file."""
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _generate(
        self,
        resume_draft_id: UUID,
        template_name: ResumeTemplateName,
        output_format: DocumentFormat,
        output_directory: Path | None,
    ) -> DocumentGenerationResult:
        """Build a typed request for a convenience generation method."""
        return self.generate_from_resume_draft(
            DocumentGenerationRequest(
                resume_draft_id=resume_draft_id,
                template_name=template_name,
                output_format=output_format,
                output_directory=output_directory,
            )
        )

    def _require_approved_draft(self, resume_draft_id: UUID) -> ResumeDraft:
        """Load one structured draft and enforce the review boundary."""
        draft = self.drafts.get(resume_draft_id)
        if draft is None:
            raise ResumeDraftNotFoundError(f"resume draft {resume_draft_id} was not found")
        if draft.status != ResumeDraftStatus.APPROVED:
            raise ResumeDraftNotApprovedError(
                f"resume draft {resume_draft_id} must be approved before generation"
            )
        return draft

    def _require_candidate(self, candidate_profile_id: UUID) -> CandidateProfile:
        """Load candidate identity for resume headers."""
        candidate = self.session.get(CandidateProfile, candidate_profile_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate

    def _require_exporter(self, output_format: DocumentFormat) -> DocumentExporter:
        """Return a configured local exporter for the requested format."""
        exporter = self.exporters.get(output_format)
        if exporter is None:
            raise UnsupportedDocumentFormatError(
                f"document format {output_format} is not configured"
            )
        return exporter

    @staticmethod
    def _file_name(
        candidate: CandidateProfile,
        draft: ResumeDraft,
        template_name: ResumeTemplateName,
        exporter: DocumentExporter,
        document_id: UUID,
    ) -> str:
        """Create a readable collision-resistant local filename."""
        stem = "-".join(
            _slug(value)
            for value in (candidate.full_name, draft.target_role, str(template_name))
            if value
        )
        return f"{stem}-{str(document_id)[:8]}{exporter.extension}"

    def _record_failure(
        self, document: GeneratedDocument, output_path: Path, error: Exception
    ) -> None:
        """Persist a failed generation attempt and remove a partial file."""
        if output_path.exists():
            output_path.unlink()
        self.documents.update(
            document,
            {
                "generation_status": str(DocumentGenerationStatus.FAILED),
                "error_message": str(error),
            },
        )
        self._commit()

    def _commit(self) -> None:
        """Commit generated-document metadata and rollback consistently."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


def _slug(value: str) -> str:
    """Return a portable lowercase filename segment."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or "resume"
