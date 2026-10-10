"""Tests for the local development candidate seed."""

import unittest

from sqlalchemy import func, select

from app.models import CandidateProfile, Skill
from scripts.seed_candidate import SKILLS, seed_candidate
from tests.support import create_test_engine, create_test_session


class SeedCandidateTests(unittest.TestCase):
    """Verify that the seed builds a pipeline-ready candidate aggregate."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_seed_candidate_builds_complete_early_career_profile(self) -> None:
        profile = seed_candidate(self.session)

        self.assertEqual(profile.full_name, "Amina Rahman")
        self.assertEqual(len(profile.education), 1)
        self.assertEqual(len(profile.work_experiences), 2)
        self.assertEqual(len(profile.projects), 4)
        self.assertEqual(len(profile.skills), len(SKILLS))
        self.assertEqual(len(profile.certifications), 1)
        self.assertIsNotNone(profile.career_goals)
        self.assertIsNotNone(profile.preferences)
        self.assertIn("FastAPI", {skill.name for skill in profile.skills})
        self.assertIn("LangGraph", {skill.name for skill in profile.skills})
        self.assertIn("AI Workflow Engineer", profile.career_goals.target_roles)

    def test_seed_candidate_is_idempotent(self) -> None:
        first = seed_candidate(self.session)
        second = seed_candidate(self.session)

        self.assertEqual(second.id, first.id)
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(CandidateProfile)),
            1,
        )
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(Skill)),
            len(SKILLS),
        )


if __name__ == "__main__":
    unittest.main()
