"""Repository tests for job-description and analysis persistence."""

import unittest

from app.models import JobAnalysis, JobDescription, SeniorityLevel
from app.repositories import JobAnalysisRepository, JobDescriptionRepository
from tests.support import create_test_engine, create_test_session


class JobAnalysisRepositoryTests(unittest.TestCase):
    """Exercise storage, revision selection, listing, and search behavior."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.jobs = JobDescriptionRepository(self.session)
        self.analyses = JobAnalysisRepository(self.session)
        self.job = self.jobs.add(
            JobDescription(
                raw_job_title="AI Engineer",
                company_name="Example Labs",
                location="Remote",
                source_platform="LinkedIn",
                description_text="Build AI services with Python and FastAPI.",
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_and_returns_latest_analysis_revision(self) -> None:
        first = self._create_analysis(revision=1, summary="First analysis")
        latest = self._create_analysis(revision=2, summary="Updated analysis")
        self.session.commit()

        self.assertEqual(self.analyses.next_revision(self.job.id), 3)
        self.assertNotEqual(first.id, latest.id)
        self.assertEqual(
            self.analyses.get_latest_for_job_description(self.job.id).id,
            latest.id,
        )

    def test_search_latest_analysis_by_keyword_and_platform(self) -> None:
        self._create_analysis(
            revision=1,
            summary="AI engineering role",
            ats_keywords=["Python", "FastAPI", "Generative AI"],
        )
        self.session.commit()

        matching = self.analyses.search_latest(keyword="Generative AI", platform="linked")

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0][0].id, self.job.id)

    def test_list_latest_returns_one_revision_per_job(self) -> None:
        self._create_analysis(revision=1, summary="First analysis")
        self._create_analysis(revision=2, summary="Updated analysis")
        self.session.commit()

        matching = self.analyses.list_latest()

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0][1].revision, 2)

    def _create_analysis(
        self,
        *,
        revision: int,
        summary: str,
        ats_keywords: list[str] | None = None,
    ) -> JobAnalysis:
        """Persist a compact analysis fixture."""
        return self.analyses.add(
            JobAnalysis(
                job_description_id=self.job.id,
                revision=revision,
                analyzer_name="rule_based",
                analyzer_version="test",
                normalized_job_title="AI Engineer",
                seniority_level=SeniorityLevel.MID,
                ats_keywords=ats_keywords or [],
                job_summary=summary,
            )
        )
