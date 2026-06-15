"""Service tests for the lightweight application tracker."""

import unittest
from decimal import Decimal
from uuid import uuid4

from app.models import (
    CandidateProfile,
    GeneratedDocument,
    JobAnalysis,
    JobDescription,
    ResumeAnalysis,
    ResumeDraft,
)
from app.models.enums import (
    ApplicationStatus,
    DocumentFormat,
    DocumentGenerationStatus,
    ResumeDraftStatus,
    ResumeTemplateName,
    SeniorityLevel,
)
from app.schemas import ApplicationRecordCreate
from app.services import (
    ApplicationRecordNotFoundError,
    ApplicationTrackerService,
    InvalidApplicationReferenceError,
)
from tests.support import create_test_engine, create_test_session, create_test_user


class ApplicationTrackerServiceTests(unittest.TestCase):
    """Verify the narrow applied or not-applied tracker workflow."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.user = create_test_user(self.session)
        self.profile = CandidateProfile(user_id=self.user.id, full_name="Grace Hopper")
        self.description = JobDescription(
            raw_title="Backend Engineer",
            company_name="Platform Labs",
            description_text="Build reliable APIs.",
            job_url="https://example.com/jobs/backend",
        )
        self.analysis = JobAnalysis(
            job_description=self.description,
            revision=1,
            analyzer_name="rule_based",
            analyzer_version="test",
            normalized_title="Backend Engineer",
            seniority_level=SeniorityLevel.SENIOR,
            job_summary="Backend engineering role.",
        )
        resume_analysis = ResumeAnalysis(
            candidate_profile=self.profile,
            job_analysis=self.analysis,
            overall_match_score=Decimal("80"),
            keyword_match_score=Decimal("80"),
            skills_match_score=Decimal("80"),
            technology_match_score=Decimal("80"),
            experience_match_score=Decimal("80"),
            project_match_score=Decimal("80"),
            education_match_score=Decimal("50"),
            suggested_resume_summary="Backend engineer.",
        )
        draft = ResumeDraft(
            resume_analysis=resume_analysis,
            candidate_profile=self.profile,
            job_analysis=self.analysis,
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Backend engineer.",
            status=ResumeDraftStatus.APPROVED,
        )
        self.document = GeneratedDocument(
            resume_draft=draft,
            candidate_profile=self.profile,
            job_analysis=self.analysis,
            template_name=ResumeTemplateName.CLEAN_ATS,
            output_format=DocumentFormat.PDF,
            file_name="resume.pdf",
            file_path="generated/resumes/resume.pdf",
            generation_status=DocumentGenerationStatus.COMPLETED,
        )
        self.session.add(self.document)
        self.session.commit()
        self.service = ApplicationTrackerService(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_create_defaults_to_not_applied_and_lists_by_status(self) -> None:
        record = self._create_record()

        self.assertEqual(record.status, ApplicationStatus.NOT_APPLIED)
        self.assertIsNone(record.applied_at)
        self.assertEqual(self.service.list_candidate_applications(self.profile.id), [record])
        self.assertEqual(self.service.list_not_applied_applications(self.profile.id), [record])
        self.assertEqual(self.service.list_applied_applications(self.profile.id), [])

    def test_marking_applied_sets_timestamp_once_and_not_applied_clears_it(self) -> None:
        record = self._create_record()
        applied = self.service.mark_as_applied(record.id)
        applied_again = self.service.mark_as_applied(record.id)

        self.assertIsNotNone(applied.applied_at)
        self.assertEqual(applied_again.applied_at, applied.applied_at)
        not_applied = self.service.mark_as_not_applied(record.id)
        self.assertEqual(not_applied.status, ApplicationStatus.NOT_APPLIED)
        self.assertIsNone(not_applied.applied_at)

    def test_attaches_generated_resume_and_searches_company_or_role(self) -> None:
        record = self._create_record()
        attached = self.service.attach_resume_document(record.id, self.document.id)

        self.assertEqual(attached.generated_document_id, self.document.id)
        self.assertEqual(self.service.search_applications("Platform"), [attached])
        self.assertEqual(self.service.search_applications("Backend"), [attached])

    def test_rejects_missing_record_and_document_from_another_candidate(self) -> None:
        with self.assertRaises(ApplicationRecordNotFoundError):
            self.service.mark_as_applied(uuid4())

        record = self._create_record()
        other_profile = CandidateProfile(user_id=self.user.id, full_name="Other Candidate")
        self.session.add(other_profile)
        self.session.flush()
        self.document.candidate_profile = other_profile
        self.session.commit()
        with self.assertRaises(InvalidApplicationReferenceError):
            self.service.attach_resume_document(record.id, self.document.id)

    def _create_record(self):
        """Create one linked tracker record."""
        return self.service.create_application_record(
            ApplicationRecordCreate(
                candidate_profile_id=self.profile.id,
                job_description_id=self.description.id,
                job_analysis_id=self.analysis.id,
                company_name="Platform Labs",
                role_title="Backend Engineer",
                company_email="careers@platform.example",
                job_url=self.description.job_url,
            )
        )


if __name__ == "__main__":
    unittest.main()
