"""Repository tests for lightweight application records."""

import unittest
from datetime import UTC, datetime

from app.models import CandidateProfile
from app.models.enums import ApplicationStatus
from app.repositories import ApplicationRecordRepository
from tests.support import create_test_engine, create_test_session


class ApplicationRecordRepositoryTests(unittest.TestCase):
    """Exercise tracker CRUD, statuses, attachment, listing, and search."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.repository = ApplicationRecordRepository(self.session)
        self.profile = CandidateProfile(full_name="Ada Lovelace")
        self.session.add(self.profile)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_creates_lists_searches_and_updates_status(self) -> None:
        applied_at = datetime.now(UTC)
        first = self.repository.create(
            candidate_profile_id=self.profile.id,
            company_name="Analytical Engines",
            role_title="Python Engineer",
        )
        second = self.repository.create(
            candidate_profile_id=self.profile.id,
            company_name="Example Corp",
            role_title="Automation Engineer",
        )
        self.repository.update_status(
            second,
            ApplicationStatus.APPLIED,
            applied_at=applied_at,
        )
        self.session.commit()

        self.assertEqual(first.status, ApplicationStatus.NOT_APPLIED)
        self.assertEqual(self.repository.get_by_id(first.id), first)
        self.assertEqual(len(self.repository.list_by_candidate(self.profile.id)), 2)
        self.assertEqual(
            self.repository.list_applied(candidate_profile_id=self.profile.id), [second]
        )
        self.assertEqual(
            self.repository.list_not_applied(candidate_profile_id=self.profile.id), [first]
        )
        self.assertEqual(
            self.repository.search_by_company_or_role(
                "Python", candidate_profile_id=self.profile.id
            ),
            [first],
        )
        self.assertEqual(second.applied_at, applied_at)


if __name__ == "__main__":
    unittest.main()
