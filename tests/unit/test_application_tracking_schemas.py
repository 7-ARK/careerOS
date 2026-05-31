"""Schema tests for the lightweight application tracker."""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.models.enums import ApplicationStatus
from app.schemas import ApplicationRecordCreate, ApplicationRecordUpdate


class ApplicationTrackingSchemaTests(unittest.TestCase):
    """Verify strict two-state tracker validation."""

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

    def test_rejects_legacy_pipeline_statuses(self) -> None:
        with self.assertRaises(ValidationError):
            ApplicationRecordCreate(
                candidate_profile_id=uuid4(),
                company_name="Example Corp",
                role_title="Backend Engineer",
                status=ApplicationStatus.INTERVIEWING,
            )
        with self.assertRaises(ValidationError):
            ApplicationRecordUpdate(status=ApplicationStatus.REJECTED)


if __name__ == "__main__":
    unittest.main()
