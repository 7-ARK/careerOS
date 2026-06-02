"""Schema tests for manually imported job postings."""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.models.enums import SourcePlatform
from app.schemas import ManualJobImportRequest


class ManualJobImportSchemaTests(unittest.TestCase):
    """Verify strict validation for manually pasted job data."""

    def test_normalizes_platform_and_currency(self) -> None:
        request = self._request(source_platform="LinkedIn", currency="usd")

        self.assertEqual(request.source_platform, SourcePlatform.LINKEDIN)
        self.assertEqual(request.currency, "USD")
        self.assertTrue(request.create_application_record)

    def test_rejects_empty_required_text(self) -> None:
        for field in ("raw_title", "company_name", "description_text"):
            values = {field: " "}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self._request(**values)

    def test_rejects_bad_url_and_company_email(self) -> None:
        with self.assertRaises(ValidationError):
            self._request(job_url="not-a-url")
        with self.assertRaises(ValidationError):
            self._request(company_email="not-an-email")

    def test_rejects_inverted_salary_range(self) -> None:
        with self.assertRaises(ValidationError):
            self._request(salary_min=200000, salary_max=100000)

    @staticmethod
    def _request(**overrides: object) -> ManualJobImportRequest:
        """Build a valid request with optional test overrides."""
        values = {
            "candidate_profile_id": uuid4(),
            "raw_title": "Backend Engineer",
            "company_name": "Platform Labs",
            "description_text": "Build Python APIs.",
        }
        values.update(overrides)
        return ManualJobImportRequest(**values)


if __name__ == "__main__":
    unittest.main()
