"""Unit tests for deterministic local job-description extraction."""

import unittest

from app.features.job_analysis import RuleBasedJobAnalyzer
from app.models import JobWorkplaceType, SeniorityLevel
from app.schemas import JobDescriptionAnalysisInput

AI_ENGINEER_DESCRIPTION = """
Responsibilities:
- Design and build production-grade generative AI services and REST APIs.
- Collaborate with product and engineering teams to deliver reliable systems.
- Optimize LLM applications using retrieval-augmented generation.

Requirements:
- 5+ years of experience in backend development or machine learning.
- Strong Python, FastAPI, PostgreSQL, Docker, AWS, and Kubernetes experience.
- Experience with large language models, prompt engineering, and vector databases.
- Excellent communication and problem-solving skills.

Preferred qualifications:
- LangGraph or OpenAI experience is a plus.
- Knowledge of FinTech platforms is preferred.

This is a hybrid role.
"""


class RuleBasedJobAnalyzerTests(unittest.TestCase):
    """Verify stable software and AI extraction behavior."""

    def setUp(self) -> None:
        self.analyzer = RuleBasedJobAnalyzer()

    def test_extracts_common_ai_and_software_keywords(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionAnalysisInput(
                raw_job_title="Sr. AI Backend Engineer (Hybrid)",
                company_name="Example Labs",
                description_text=AI_ENGINEER_DESCRIPTION,
            )
        )

        self.assertEqual(result.normalized_job_title, "Senior AI Backend Engineer")
        self.assertEqual(result.seniority_level, SeniorityLevel.SENIOR)
        self.assertEqual(result.estimated_experience_level, "5+ years")
        self.assertIn("Machine Learning", result.required_skills)
        self.assertIn("Large Language Models", result.required_skills)
        self.assertIn("Python", result.required_technologies)
        self.assertIn("FastAPI", result.required_technologies)
        self.assertIn("LangGraph", result.preferred_technologies)
        self.assertIn("OpenAI", result.preferred_technologies)
        self.assertIn("Communication", result.soft_skills)
        self.assertIn("FinTech", result.domain_keywords)
        self.assertEqual(result.match_relevant_signals["workplace_type"], "hybrid")
        self.assertTrue(result.match_relevant_signals["scoring_ready"])

    def test_weak_description_returns_missing_information(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionAnalysisInput(
                raw_job_title="Developer",
                company_name="Example Corp",
                description_text="Python developer.",
            )
        )

        self.assertIn("detailed job description", result.missing_information)
        self.assertIn("responsibilities", result.missing_information)
        self.assertIn("qualifications", result.missing_information)
        self.assertIn("experience requirement", result.missing_information)
        self.assertIn("Python", result.required_technologies)

    def test_flags_explicit_warning_phrases(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionAnalysisInput(
                raw_job_title="Software Engineer",
                company_name="Example Corp",
                description_text=(
                    "We need a rockstar willing to wear many hats in an always on culture."
                ),
                workplace_type=JobWorkplaceType.REMOTE,
            )
        )

        self.assertIn("Uses vague 'rockstar' language", result.red_flags)
        self.assertIn("Suggests an unusually broad role scope", result.red_flags)
        self.assertIn("May imply an always-on availability expectation", result.red_flags)
