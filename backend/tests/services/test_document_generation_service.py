"""Service tests for local Markdown, DOCX, and PDF resume generation."""

import hashlib
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.features.document_generation import DocumentGenerationService
from app.features.document_generation.exporters import DocumentExporter
from app.features.document_generation.templates import RenderedResume
from app.models import CandidateProfile, JobAnalysis, JobDescription, ResumeAnalysis, ResumeDraft
from app.models.enums import (
    DocumentFormat,
    DocumentGenerationStatus,
    ResumeDraftStatus,
    ResumeTemplateName,
    SeniorityLevel,
)
from app.schemas import DocumentGenerationRequest
from app.services import (
    DocumentGenerationError,
    ResumeDraftNotApprovedError,
    ResumeDraftNotFoundError,
    UnsupportedDocumentFormatError,
)
from tests.support import create_test_engine, create_test_session, create_test_user


class FailingMarkdownExporter(DocumentExporter):
    """Write a partial file before simulating an exporter failure."""

    output_format = DocumentFormat.MARKDOWN
    extension = ".md"

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Create a partial file and fail deterministically."""
        output_path.write_text(resume.full_name, encoding="utf-8")
        raise RuntimeError("simulated exporter failure")


class DocumentGenerationServiceTests(unittest.TestCase):
    """Verify real local exports, checksums, metadata, and defensive boundaries."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.output_directory = Path(self.temporary_directory.name)
        user = create_test_user(self.session)
        self.profile = CandidateProfile(
            user_id=user.id,
            full_name="Grace Hopper",
            email="grace@example.com",
            location="New York",
        )
        description = JobDescription(raw_title="Backend Engineer", description_text="Build APIs.")
        self.job_analysis = JobAnalysis(
            job_description=description,
            revision=1,
            analyzer_name="rule_based",
            analyzer_version="test",
            normalized_title="Backend Engineer",
            seniority_level=SeniorityLevel.SENIOR,
            job_summary="Backend engineering role.",
        )
        analysis = ResumeAnalysis(
            candidate_profile=self.profile,
            job_analysis=self.job_analysis,
            overall_match_score=Decimal("80"),
            keyword_match_score=Decimal("80"),
            skills_match_score=Decimal("80"),
            technology_match_score=Decimal("80"),
            experience_match_score=Decimal("80"),
            project_match_score=Decimal("80"),
            education_match_score=Decimal("50"),
            suggested_resume_summary="Backend engineer with Python experience.",
        )
        self.draft = ResumeDraft(
            resume_analysis=analysis,
            candidate_profile=self.profile,
            job_analysis=self.job_analysis,
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Backend engineer with evidence-backed Python experience.",
            skills_section=[{"name": "Python", "category": "Programming"}],
            experience_section=[
                {
                    "job_title": "Backend Engineer",
                    "company": "Example Corp",
                    "start_date": "2020-01-01",
                    "description": "Built Python services.",
                    "achievements": ["Delivered reliable APIs"],
                }
            ],
            projects_section=[
                {
                    "title": "Commerce API",
                    "technologies": ["Python", "FastAPI"],
                    "description": "Built a commerce API.",
                    "outcomes": ["Improved reliability"],
                }
            ],
            omitted_keywords=["Kubernetes"],
            truthfulness_notes=["Do not claim Kubernetes."],
            status=ResumeDraftStatus.APPROVED,
        )
        self.session.add(self.draft)
        self.session.commit()
        self.service = DocumentGenerationService(
            self.session, output_directory=self.output_directory
        )

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_generate_markdown_persists_checksum_and_excludes_internal_notes(self) -> None:
        result = self.service.generate_markdown(self.draft.id)
        path = Path(result.document.file_path)
        expected_checksum = hashlib.sha256(path.read_bytes()).hexdigest()

        self.assertTrue(path.exists())
        self.assertEqual(path.suffix, ".md")
        self.assertEqual(result.document.generation_status, DocumentGenerationStatus.COMPLETED)
        self.assertEqual(result.document.checksum, expected_checksum)
        self.assertEqual(result.document.file_size_bytes, path.stat().st_size)
        self.assertNotIn("Kubernetes", path.read_text(encoding="utf-8"))
        self.assertEqual(self.service.get_generated_document(result.document.id), result.document)
        self.assertEqual(
            self.service.list_documents_by_candidate(self.profile.id), [result.document]
        )
        self.assertEqual(self.service.list_documents_by_draft(self.draft.id), [result.document])

    def test_generate_docx_creates_editable_zip_document(self) -> None:
        result = self.service.generate_docx(
            self.draft.id, template_name=ResumeTemplateName.MODERN_PROFESSIONAL
        )

        self.assertEqual(result.document.output_format, DocumentFormat.DOCX)
        self.assertTrue(zipfile.is_zipfile(result.document.file_path))

    def test_generate_pdf_creates_selectable_text_pdf(self) -> None:
        result = self.service.generate_pdf(self.draft.id)

        self.assertEqual(result.document.output_format, DocumentFormat.PDF)
        self.assertTrue(Path(result.document.file_path).read_bytes().startswith(b"%PDF"))

    def test_rejects_missing_and_unapproved_drafts(self) -> None:
        with self.assertRaises(ResumeDraftNotFoundError):
            self.service.generate_markdown(uuid4())

        self.draft.status = ResumeDraftStatus.REVIEWED
        self.session.commit()
        with self.assertRaises(ResumeDraftNotApprovedError):
            self.service.generate_markdown(self.draft.id)

    def test_rejects_format_without_configured_exporter(self) -> None:
        service = DocumentGenerationService(
            self.session,
            output_directory=self.output_directory,
            exporters={},
        )

        with self.assertRaises(UnsupportedDocumentFormatError):
            service.generate_from_resume_draft(
                DocumentGenerationRequest(
                    resume_draft_id=self.draft.id,
                    output_format=DocumentFormat.PDF,
                )
            )

    def test_records_failed_generation_and_removes_partial_file(self) -> None:
        service = DocumentGenerationService(
            self.session,
            output_directory=self.output_directory,
            exporters={DocumentFormat.MARKDOWN: FailingMarkdownExporter()},
        )

        with self.assertRaises(DocumentGenerationError):
            service.generate_markdown(self.draft.id)

        documents = service.list_documents_by_draft(self.draft.id)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].generation_status, DocumentGenerationStatus.FAILED)
        self.assertIn("simulated exporter failure", documents[0].error_message)
        self.assertFalse(Path(documents[0].file_path).exists())


if __name__ == "__main__":
    unittest.main()
