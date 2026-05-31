"""Service tests for API-ready job analysis workflows."""

import unittest
from uuid import uuid4

from app.schemas import JobAnalysisListFilters, JobDescriptionCreate
from app.services import (
    JobAnalysisNotFoundError,
    JobAnalyzerService,
    JobDescriptionNotFoundError,
)
from tests.support import create_test_engine, create_test_session
from tests.unit.test_rule_based_job_analyzer import AI_ENGINEER_DESCRIPTION


class JobAnalyzerServiceTests(unittest.TestCase):
    """Verify capture, analysis, retrieval, revisioning, and discovery."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.service = JobAnalyzerService(self.session)
        self.job = self.service.create_job_description(
            JobDescriptionCreate(
                raw_job_title="Sr. AI Backend Engineer",
                company_name="Example Labs",
                location="Karachi",
                source_platform="LinkedIn",
                description_text=AI_ENGINEER_DESCRIPTION,
            )
        )

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_analyze_stores_and_retrieves_latest_revision(self) -> None:
        first = self.service.analyze_job_description(self.job.id)
        second = self.service.analyze_job_description(self.job.id)
        retrieved = self.service.get_analysis_by_job_description_id(self.job.id)

        self.assertEqual(first.revision, 1)
        self.assertEqual(second.revision, 2)
        self.assertEqual(retrieved.id, second.id)
        self.assertIn("Python", retrieved.required_technologies)

    def test_list_and_search_analyzed_jobs(self) -> None:
        self.service.analyze_job_description(self.job.id)

        listed = self.service.list_analyzed_jobs()
        searched = self.service.search_analyzed_jobs(
            JobAnalysisListFilters(keyword="LangGraph", platform="LinkedIn", location="Karachi")
        )

        self.assertEqual(len(listed), 1)
        self.assertEqual(len(searched), 1)
        self.assertEqual(searched[0].job_description.company_name, "Example Labs")

    def test_get_analysis_requires_existing_analysis(self) -> None:
        with self.assertRaises(JobAnalysisNotFoundError):
            self.service.get_analysis_by_job_description_id(self.job.id)

    def test_analyze_requires_existing_job_description(self) -> None:
        with self.assertRaises(JobDescriptionNotFoundError):
            self.service.analyze_job_description(uuid4())
