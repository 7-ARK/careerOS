"""Unit tests for candidate knowledge-base validation."""

import unittest
from datetime import date
from decimal import Decimal

from pydantic import ValidationError

from app.schemas import CareerGoalCreate, ProjectCreate, SkillCreate, WorkExperienceCreate


class KnowledgeBaseSchemaTests(unittest.TestCase):
    """Verify important command validation rules."""

    def test_skill_rating_must_be_in_supported_range(self) -> None:
        with self.assertRaises(ValidationError):
            SkillCreate(
                name="Python",
                category="Programming",
                self_rating=6,
                years_of_experience=Decimal("4.5"),
            )

    def test_project_end_date_cannot_precede_start_date(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectCreate(
                title="careerOS",
                description="Career operating system",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 1, 1),
            )

    def test_salary_max_cannot_be_lower_than_minimum(self) -> None:
        with self.assertRaises(ValidationError):
            CareerGoalCreate(salary_min=Decimal("150000"), salary_max=Decimal("100000"))

    def test_experience_accepts_current_role_without_end_date(self) -> None:
        experience = WorkExperienceCreate(
            company="Example Corp",
            job_title="Staff Engineer",
            start_date=date(2024, 1, 1),
            is_current=True,
        )

        self.assertIsNone(experience.end_date)
