"""Repository tests for resume analyses and structured drafts."""

import unittest
from decimal import Decimal

from app.models import CandidateProfile, JobAnalysis, JobDescription, ResumeAnalysis
from app.models.enums import ResumeDraftStatus, SeniorityLevel
from app.repositories import ResumeAnalysisRepository, ResumeDraftRepository
from tests.support import create_test_engine, create_test_session


class ResumeIntelligenceRepositoryTests(unittest.TestCase):
    """Exercise persistence, latest queries, list filters, and draft status updates."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.analyses = ResumeAnalysisRepository(self.session)
        self.drafts = ResumeDraftRepository(self.session)
        self.profile = CandidateProfile(full_name="Ada Lovelace")
        self.job_description = JobDescription(
            raw_title="Backend Engineer",
            description_text="Build Python services.",
        )
        self.job_analysis = JobAnalysis(
            job_description=self.job_description,
            revision=1,
            analyzer_name="rule_based",
            analyzer_version="test",
            normalized_title="Backend Engineer",
            seniority_level=SeniorityLevel.MID_LEVEL,
            job_summary="Backend engineering role.",
        )
        self.session.add_all([self.profile, self.job_analysis])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_analysis_and_structured_draft(self) -> None:
        first = self._create_analysis(summary="First summary")
        latest = self._create_analysis(summary="Latest summary")
        self.session.commit()

        draft = self.drafts.create_resume_draft(
            resume_analysis_id=latest.id,
            candidate_profile_id=self.profile.id,
            job_analysis_id=self.job_analysis.id,
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Latest summary",
        )
        self.session.commit()

        self.assertEqual(
            self.analyses.get_latest_by_candidate_job(self.profile.id, self.job_analysis.id).id,
            latest.id,
        )
        self.assertEqual(len(self.analyses.list_by_candidate(self.profile.id)), 2)
        self.assertEqual(len(self.analyses.list_by_job(self.job_analysis.id)), 2)
        self.assertEqual(
            self.drafts.get_latest_by_candidate_job(self.profile.id, self.job_analysis.id).id,
            draft.id,
        )

        self.drafts.update_status(draft, ResumeDraftStatus.APPROVED)
        self.session.commit()
        self.assertEqual(draft.status, ResumeDraftStatus.APPROVED)
        self.assertNotEqual(first.id, latest.id)

    def _create_analysis(self, *, summary: str) -> ResumeAnalysis:
        """Create a compact persisted analysis fixture."""
        return self.analyses.create_resume_analysis(
            candidate_profile_id=self.profile.id,
            job_analysis_id=self.job_analysis.id,
            overall_match_score=Decimal("75"),
            keyword_match_score=Decimal("75"),
            skills_match_score=Decimal("75"),
            technology_match_score=Decimal("75"),
            experience_match_score=Decimal("75"),
            project_match_score=Decimal("75"),
            education_match_score=Decimal("50"),
            suggested_resume_summary=summary,
        )
