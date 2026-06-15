"""Service tests for the manual job-posting importer."""

import unittest

from app.models import ApplicationRecord, CandidateProfile, JobAnalysis, JobDescription
from app.models.enums import ApplicationStatus, SourcePlatform
from app.schemas import ManualJobImportRequest
from app.services import ManualJobImportService
from tests.support import create_test_engine, create_test_session, create_test_user

DESCRIPTION = """
Responsibilities:
- Build reliable Python APIs and automation workflows.

Requirements:
- Strong Python, FastAPI, and PostgreSQL experience.
"""


class ManualJobImportServiceTests(unittest.TestCase):
    """Verify manual capture, deterministic analysis, and optional tracking."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        user = create_test_user(self.session)
        self.profile = CandidateProfile(user_id=user.id, full_name="Grace Hopper")
        self.session.add(self.profile)
        self.session.commit()
        self.service = ManualJobImportService(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_imports_supported_platforms_and_creates_not_applied_record(self) -> None:
        for platform in (
            SourcePlatform.LINKEDIN,
            SourcePlatform.INDEED,
            SourcePlatform.GLASSDOOR,
            SourcePlatform.UNKNOWN,
        ):
            with self.subTest(platform=platform):
                result = self.service.import_job_posting(self._request(platform))

                self.assertEqual(result.job_description.source_platform, platform)
                self.assertEqual(result.analysis.job_description_id, result.job_description.id)
                self.assertIn("Python", result.analysis.required_technologies)
                self.assertIsNotNone(result.application_record)
                self.assertEqual(result.application_record.status, ApplicationStatus.NOT_APPLIED)
                self.assertEqual(
                    result.application_record.job_description_id,
                    result.job_description.id,
                )
                self.assertEqual(
                    result.application_record.job_analysis_id,
                    result.analysis.id,
                )

    def test_import_without_application_record_still_stores_and_analyzes_job(self) -> None:
        result = self.service.import_job_posting(
            self._request(SourcePlatform.OTHER, create_application_record=False)
        )

        self.assertIsNone(result.application_record)
        self.assertIsNotNone(self.session.get(JobDescription, result.job_description.id))
        self.assertIsNotNone(self.session.get(JobAnalysis, result.analysis.id))
        self.assertEqual(self.session.query(ApplicationRecord).count(), 0)

    def test_import_copies_optional_company_email_into_tracker_record(self) -> None:
        result = self.service.import_job_posting(
            self._request(SourcePlatform.LINKEDIN, company_email="careers@platform.example")
        )

        self.assertEqual(result.application_record.company_email, "careers@platform.example")

    def _request(
        self,
        platform: SourcePlatform,
        **overrides: object,
    ) -> ManualJobImportRequest:
        """Build a linked manual-import request."""
        values = {
            "candidate_profile_id": self.profile.id,
            "raw_title": "Backend Engineer",
            "company_name": "Platform Labs",
            "location": "Remote",
            "source_platform": platform,
            "job_url": "https://example.com/jobs/backend",
            "description_text": DESCRIPTION,
            "salary_min": 100000,
            "salary_max": 150000,
            "currency": "usd",
            "employment_type": "full_time",
            "workplace_type": "remote",
        }
        values.update(overrides)
        return ManualJobImportRequest(**values)


if __name__ == "__main__":
    unittest.main()
