"""End-to-end tests for the manual application pipeline."""

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.features.document_generation import DocumentGenerationService
from app.features.document_generation.exporters import DocumentExporter
from app.features.document_generation.templates import RenderedResume
from app.models import (
    ApplicationRecord,
    GeneratedDocument,
    ResumeAnalysis,
    ResumeDraft,
)
from app.models.enums import (
    DocumentFormat,
    DocumentGenerationStatus,
    PipelineStage,
    PipelineStatus,
    ResumeDraftStatus,
    ResumeTemplateName,
)
from app.schemas import (
    CandidateProfileCreate,
    ManualJobPipelineRequest,
    ProjectCreate,
    SkillCreate,
    WorkExperienceCreate,
)
from app.services import (
    ApplicationPipelineService,
    KnowledgeBaseService,
    PipelineExecutionError,
)
from tests.support import create_test_engine, create_test_session, create_test_user

DESCRIPTION = """
Responsibilities:
- Build reliable Python APIs and automation workflows.

Requirements:
- Strong Python, FastAPI, PostgreSQL, Docker, and Kubernetes experience.
"""


class FailingPdfExporter(DocumentExporter):
    """Create a partial file and fail to exercise pipeline error handling."""

    output_format = DocumentFormat.PDF
    extension = ".pdf"

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write a partial document before failing deterministically."""
        output_path.write_text(resume.full_name, encoding="utf-8")
        raise RuntimeError("simulated pipeline PDF failure")


class ApplicationPipelineServiceTests(unittest.TestCase):
    """Verify successful and failed end-to-end local pipeline runs."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.temporary_directory = tempfile.TemporaryDirectory()
        knowledge_base = KnowledgeBaseService(self.session)
        user = create_test_user(self.session)
        profile = knowledge_base.create_candidate_profile(
            CandidateProfileCreate(
                full_name="Grace Hopper",
                email="grace@example.com",
                headline="Backend Engineer",
            ),
            user_id=user.id,
        )
        knowledge_base.add_skill(
            profile.id,
            SkillCreate(
                name="Python",
                category="Programming",
                self_rating=5,
                years_of_experience=Decimal("6"),
            ),
        )
        knowledge_base.add_project(
            profile.id,
            ProjectCreate(
                title="Commerce API",
                description="Built reliable APIs for a commerce platform.",
                technologies=["Python", "FastAPI", "PostgreSQL", "Docker"],
                outcomes=["Improved reliability"],
            ),
        )
        knowledge_base.add_experience(
            profile.id,
            WorkExperienceCreate(
                company="Example Corp",
                job_title="Backend Engineer",
                start_date=date(2020, 1, 1),
                description="Built Python and PostgreSQL backend services.",
                achievements=["Delivered reliable APIs"],
            ),
        )
        self.profile_id = profile.id

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_runs_full_pipeline_and_links_generated_document(self) -> None:
        result = self._service().run_manual_job_pipeline(self._request())
        application = self.session.get(ApplicationRecord, result.application_record_id)

        self.assertEqual(result.status, PipelineStatus.COMPLETED)
        self.assertGreater(result.match_score, Decimal("0"))
        self.assertEqual(result.document_format, DocumentFormat.PDF)
        self.assertEqual(result.template_name, ResumeTemplateName.CLEAN_ATS)
        self.assertEqual(result.matched_skills, [])
        self.assertIn("Python", result.matched_technologies)
        self.assertIn("FastAPI", result.matched_technologies)
        self.assertIn("Kubernetes", result.missing_technologies)
        self.assertTrue(result.selected_projects)
        self.assertEqual(result.selected_projects[0]["title"], "Commerce API")
        self.assertTrue(Path(result.generated_file_path).exists())
        self.assertEqual(application.generated_document_id, result.generated_document_id)
        self.assertIn("Review the generated resume document.", result.next_actions)

    def test_pipeline_without_application_record_still_generates_document(self) -> None:
        result = self._service().run_manual_job_pipeline(
            self._request(create_application_record=False, document_format=DocumentFormat.MARKDOWN)
        )

        self.assertIsNone(result.application_record_id)
        self.assertTrue(Path(result.generated_file_path).exists())
        self.assertEqual(self.session.query(ApplicationRecord).count(), 0)

    def test_document_generation_failure_preserves_analysis_and_draft(self) -> None:
        document_generation = DocumentGenerationService(
            self.session,
            output_directory=Path(self.temporary_directory.name),
            exporters={DocumentFormat.PDF: FailingPdfExporter()},
        )
        service = ApplicationPipelineService(
            self.session,
            document_generation=document_generation,
        )

        with self.assertRaises(PipelineExecutionError) as context:
            service.run_manual_job_pipeline(self._request())

        self.assertEqual(context.exception.stage, PipelineStage.DOCUMENT_GENERATION)
        self.assertIn("simulated pipeline PDF failure", str(context.exception))
        self.assertEqual(self.session.query(ResumeAnalysis).count(), 1)
        self.assertEqual(self.session.query(ResumeDraft).one().status, ResumeDraftStatus.APPROVED)
        self.assertEqual(
            self.session.query(GeneratedDocument).one().generation_status,
            DocumentGenerationStatus.FAILED,
        )
        self.assertIsNone(self.session.query(ApplicationRecord).one().generated_document_id)

    def _service(self) -> ApplicationPipelineService:
        """Build a pipeline that writes generated files into a temporary directory."""
        return ApplicationPipelineService(
            self.session,
            document_generation=DocumentGenerationService(
                self.session,
                output_directory=Path(self.temporary_directory.name),
            ),
        )

    def _request(self, **overrides: object) -> ManualJobPipelineRequest:
        """Build a valid end-to-end request."""
        values = {
            "candidate_profile_id": self.profile_id,
            "raw_title": "Senior Backend Engineer",
            "company_name": "Platform Labs",
            "location": "Remote",
            "source_platform": "LinkedIn",
            "job_url": "https://example.com/jobs/backend",
            "description_text": DESCRIPTION,
            "company_email": "careers@platform.example",
        }
        values.update(overrides)
        return ManualJobPipelineRequest(**values)


if __name__ == "__main__":
    unittest.main()
