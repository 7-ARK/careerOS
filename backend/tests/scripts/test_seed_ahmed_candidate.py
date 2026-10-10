"""Tests for Ahmed Raza's real development candidate seed."""

import unittest

from scripts.seed_ahmed_candidate import (
    DEVELOPER_EMAIL,
    DEVELOPER_PHONE,
    SKILLS,
    seed_ahmed_candidate,
)
from tests.support import create_test_engine, create_test_session


class AhmedSeedCandidateTests(unittest.TestCase):
    """Verify that Ahmed's seed builds an honest early-career profile."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_seed_ahmed_candidate_builds_real_profile(self) -> None:
        profile = seed_ahmed_candidate(self.session)

        self.assertEqual(profile.full_name, "Ahmed Raza")
        self.assertEqual(profile.email, DEVELOPER_EMAIL)
        self.assertEqual(profile.phone, DEVELOPER_PHONE)
        self.assertEqual(profile.location, "Islamabad, Pakistan")
        self.assertEqual(
            str(profile.linkedin_url),
            "https://www.linkedin.com/in/ahmed-raza-applied-ai/",
        )
        self.assertEqual(len(profile.education), 1)
        self.assertEqual(len(profile.work_experiences), 1)
        self.assertEqual(len(profile.projects), 4)
        self.assertEqual(len(profile.skills), len(SKILLS))
        self.assertEqual(len(profile.certifications), 4)
        self.assertIn("careerOS", {project.title for project in profile.projects})
        self.assertIn("Python", {skill.name for skill in profile.skills})
        self.assertIn("AI Automation Engineer", profile.career_goals.target_roles)
        self.assertTrue(profile.preferences.resume_preferences["avoid_senior_claims"])


if __name__ == "__main__":
    unittest.main()
