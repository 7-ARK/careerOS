"""Unit tests for job-analysis schema validation."""

import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.models import WorkplaceType
from app.schemas import JobDescriptionCreate, JobDescriptionUpdate


class JobAnalysisSchemaTests(unittest.TestCase):
    """Verify source posting validation rules."""

    def test_description_text_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            JobDescriptionCreate(
                raw_title="Software Engineer",
                company_name="Example Corp",
                description_text="   ",
            )

    def test_salary_max_cannot_be_lower_than_minimum(self) -> None:
        with self.assertRaises(ValidationError):
            JobDescriptionCreate(
                raw_title="Software Engineer",
                company_name="Example Corp",
                description_text="Build reliable services.",
                salary_min=Decimal("150000"),
                salary_max=Decimal("120000"),
            )

    def test_source_capture_normalizes_currency(self) -> None:
        posting = JobDescriptionCreate(
            raw_title=" Software Engineer ",
            company_name=" Example Corp ",
            description_text="Build reliable services.",
            currency="usd",
            workplace_type=WorkplaceType.REMOTE,
        )

        self.assertEqual(posting.raw_title, "Software Engineer")
        self.assertEqual(posting.company_name, "Example Corp")
        self.assertEqual(posting.currency, "USD")

    def test_job_url_must_be_valid_when_provided(self) -> None:
        with self.assertRaises(ValidationError):
            JobDescriptionCreate(
                raw_title="Software Engineer",
                description_text="Build reliable services.",
                job_url="not-a-url",
            )

    def test_custom_platform_value_is_preserved(self) -> None:
        posting = JobDescriptionCreate(
            raw_title="Software Engineer",
            description_text="Build reliable services.",
            source_platform="Specialized Tech Board",
        )

        self.assertEqual(posting.source_platform, "specialized_tech_board")

    def test_update_schema_supports_partial_changes(self) -> None:
        update = JobDescriptionUpdate(location="Karachi")

        self.assertEqual(update.model_dump(exclude_unset=True), {"location": "Karachi"})
