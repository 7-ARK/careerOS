"""Schema tests for the lightweight application tracker."""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.models.enums import ApplicationStatus
from app.schemas import ApplicationRecordCreate, ApplicationRecordUpdate


class ApplicationTrackingSchemaTests(unittest.TestCase):
    """Verify application tracker validation."""

    def test_defaults_to_not_applied(self) -> None:
        record = ApplicationRecordCreate(
            candidate_profile_id=uuid4(),
            company_name="Example Corp",
            role_title="Backend Engineer",
        )

        self.assertEqual(record.status, ApplicationStatus.NOT_APPLIED)

    def test_rejects_empty_company_and_role(self) -> None:
        for values in (
            {"company_name": " ", "role_title": "Backend Engineer"},
            {"company_name": "Example Corp", "role_title": " "},
        ):
            with self.assertRaises(ValidationError):
                ApplicationRecordCreate(candidate_profile_id=uuid4(), **values)

    def test_validates_optional_company_email(self) -> None:
        record = ApplicationRecordCreate(
            candidate_profile_id=uuid4(),
            company_name="Example Corp",
            role_title="Backend Engineer",
            company_email="careers@example.com",
        )

        self.assertEqual(record.company_email, "careers@example.com")
        with self.assertRaises(ValidationError):
            ApplicationRecordCreate(
                candidate_profile_id=uuid4(),
                company_name="Example Corp",
                role_title="Backend Engineer",
                company_email="not-an-email",
            )

    def test_accepts_user_facing_tracker_statuses(self) -> None:
        for status in (
            ApplicationStatus.SAVED,
            ApplicationStatus.APPLIED,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.OFFER,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.ARCHIVED,
        ):
            record = ApplicationRecordCreate(
                candidate_profile_id=uuid4(),
                company_name="Example Corp",
                role_title="Backend Engineer",
                status=status,
            )
            self.assertEqual(record.status, status)

        update = ApplicationRecordUpdate(status=ApplicationStatus.REJECTED)
        self.assertEqual(update.status, ApplicationStatus.REJECTED)

    def test_rejects_unknown_tracker_statuses(self) -> None:
        with self.assertRaises(ValidationError):
            ApplicationRecordUpdate(status="paused")


if __name__ == "__main__":
    unittest.main()
