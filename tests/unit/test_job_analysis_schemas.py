"""Unit tests for job-analysis schema validation."""

import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.models import JobWorkplaceType
from app.schemas import JobDescriptionCreate, JobDescriptionUpdate


class JobAnalysisSchemaTests(unittest.TestCase):
    """Verify source posting validation rules."""

    def test_description_text_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            JobDescriptionCreate(
                raw_job_title="Software Engineer",
                company_name="Example Corp",
                description_text="   ",
            )

    def test_salary_max_cannot_be_lower_than_minimum(self) -> None:
        with self.assertRaises(ValidationError):
            JobDescriptionCreate(
                raw_job_title="Software Engineer",
                company_name="Example Corp",
                description_text="Build reliable services.",
                salary_min=Decimal("150000"),
                salary_max=Decimal("120000"),
            )

    def test_source_capture_normalizes_currency(self) -> None:
        posting = JobDescriptionCreate(
            raw_job_title=" Software Engineer ",
            company_name=" Example Corp ",
            description_text="Build reliable services.",
            salary_currency="usd",
            workplace_type=JobWorkplaceType.REMOTE,
        )

        self.assertEqual(posting.raw_job_title, "Software Engineer")
        self.assertEqual(posting.company_name, "Example Corp")
        self.assertEqual(posting.salary_currency, "USD")

    def test_update_schema_supports_partial_changes(self) -> None:
        update = JobDescriptionUpdate(location="Karachi")

        self.assertEqual(update.model_dump(exclude_unset=True), {"location": "Karachi"})
