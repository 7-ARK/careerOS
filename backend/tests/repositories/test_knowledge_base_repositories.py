"""Repository tests for candidate knowledge-base persistence."""

import unittest
from datetime import date
from decimal import Decimal

from app.models import (
    ApplicationHistory,
    ApplicationStatus,
)
from app.repositories import (
    ApplicationHistoryRepository,
    CandidateProfileRepository,
    SkillRepository,
)
from tests.support import create_test_engine, create_test_session, create_test_user


class KnowledgeBaseRepositoryTests(unittest.TestCase):
    """Exercise CRUD, search, and filtering through SQLAlchemy repositories."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.profiles = CandidateProfileRepository(self.session)
        self.skills = SkillRepository(self.session)
        self.applications = ApplicationHistoryRepository(self.session)
        user = create_test_user(self.session)
        self.profile = self.profiles.create(
            user_id=user.id,
            full_name="Ada Lovelace",
            email="ada@example.com",
            headline="Platform Engineer",
            location="London",
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_crud_and_filter_owned_skill(self) -> None:
        skill = self.skills.create(
            profile_id=self.profile.id,
            name="Python",
            category="Programming",
            self_rating=5,
            years_of_experience=Decimal("6.00"),
        )
        self.session.commit()

        matching = self.skills.list_for_profile(
            self.profile.id,
            filters={"category": "Programming"},
        )
        self.assertEqual([item.id for item in matching], [skill.id])

        self.skills.update(skill, {"self_rating": 4})
        self.session.commit()
        self.assertEqual(self.skills.get(skill.id).self_rating, 4)

        self.skills.delete(skill)
        self.session.commit()
        self.assertIsNone(self.skills.get(skill.id))

    def test_search_profiles_by_headline(self) -> None:
        matching = self.profiles.search_profiles("platform", location="London")

        self.assertEqual([profile.id for profile in matching], [self.profile.id])

    def test_filter_applications_by_status(self) -> None:
        self.applications.add(
            ApplicationHistory(
                profile_id=self.profile.id,
                company="Analytical Engines Ltd",
                job_title="Senior Engineer",
                application_date=date(2026, 5, 1),
                status=ApplicationStatus.INTERVIEWING,
            )
        )
        self.applications.add(
            ApplicationHistory(
                profile_id=self.profile.id,
                company="Difference Systems",
                job_title="Senior Engineer",
                application_date=date(2026, 5, 2),
                status=ApplicationStatus.REJECTED,
            )
        )
        self.session.commit()

        matching = self.applications.filter_for_profile(
            self.profile.id,
            status=ApplicationStatus.INTERVIEWING,
        )

        self.assertEqual([item.company for item in matching], ["Analytical Engines Ltd"])
