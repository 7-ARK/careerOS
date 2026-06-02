"""Unit tests for resume-intelligence schema validation."""

import unittest
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError

from app.schemas import ResumeAnalysisCreate, ResumeDraftCreate


class ResumeIntelligenceSchemaTests(unittest.TestCase):
    """Verify score bounds and structured draft defaults."""

    def test_resume_analysis_scores_must_stay_within_percentage_range(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeAnalysisCreate(
                candidate_profile_id=uuid4(),
                job_analysis_id=uuid4(),
                overall_match_score=Decimal("101"),
                keyword_match_score=Decimal("0"),
                skills_match_score=Decimal("0"),
                technology_match_score=Decimal("0"),
                experience_match_score=Decimal("0"),
                project_match_score=Decimal("0"),
                education_match_score=Decimal("0"),
                suggested_resume_summary="Summary",
            )

    def test_resume_draft_sections_default_to_empty_lists(self) -> None:
        draft = ResumeDraftCreate(
            resume_analysis_id=uuid4(),
            candidate_profile_id=uuid4(),
            job_analysis_id=uuid4(),
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Evidence-backed summary.",
        )

        self.assertEqual(draft.skills_section, [])
        self.assertEqual(draft.ats_keywords_used, [])
        self.assertEqual(draft.truthfulness_notes, [])
