"""Unit tests for deterministic local job-description extraction."""

import unittest
from inspect import isabstract

from app.features.job_analysis import FutureOpenAIJobAnalyzer, RuleBasedJobAnalyzer
from app.models import SeniorityLevel, WorkplaceType
from app.schemas import JobDescriptionInput

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
            JobDescriptionInput(
                raw_title="Sr. AI Backend Engineer (Hybrid)",
                company_name="Example Labs",
                description_text=AI_ENGINEER_DESCRIPTION,
            )
        )

        self.assertEqual(result.normalized_title, "Senior AI Backend Engineer")
        self.assertEqual(result.seniority_level, SeniorityLevel.SENIOR)
        self.assertEqual(result.estimated_years_min, 5)
        self.assertIsNone(result.estimated_years_max)
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
            JobDescriptionInput(
                raw_title="Developer",
                description_text="Python developer.",
            )
        )

        self.assertIn("detailed job description", result.missing_information)
        self.assertIn("company name", result.missing_information)
        self.assertIn("location", result.missing_information)
        self.assertIn("responsibilities", result.missing_information)
        self.assertIn("qualifications", result.missing_information)
        self.assertIn("experience requirement", result.missing_information)
        self.assertIn("Python", result.required_technologies)

    def test_flags_explicit_warning_phrases(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionInput(
                raw_title="Software Engineer",
                company_name="Example Corp",
                description_text=(
                    "We need a rockstar willing to wear many hats in an always on culture."
                ),
                workplace_type=WorkplaceType.REMOTE,
            )
        )

        self.assertIn("Uses vague 'rockstar' language", result.red_flags)
        self.assertIn("Suggests an unusually broad role scope", result.red_flags)
        self.assertIn("May imply an always-on availability expectation", result.red_flags)

    def test_extracts_automation_and_scraping_keywords(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionInput(
                raw_title="Automation Engineer",
                company_name="Example Commerce",
                description_text=(
                    "Responsibilities:\n"
                    "- Build scraping workflows with Playwright, Selenium, BeautifulSoup, "
                    "webhooks, n8n, Zapier, Make.com, Slack, and Amazon Seller Central.\n"
                    "Requirements:\n"
                    "- Experience creating automation agents and embeddings."
                ),
            )
        )

        self.assertIn("Playwright", result.required_technologies)
        self.assertIn("Selenium", result.required_technologies)
        self.assertIn("BeautifulSoup", result.required_technologies)
        self.assertIn("n8n", result.required_technologies)
        self.assertIn("Automation", result.required_skills)
        self.assertIn("Web Scraping", result.required_skills)
        self.assertIn("AI Agents", result.required_skills)

    def test_flags_unrealistic_junior_experience_requirement(self) -> None:
        result = self.analyzer.analyze(
            JobDescriptionInput(
                raw_title="Junior Software Engineer",
                description_text="Requirements:\n- 7+ years of experience in Python.",
            )
        )

        self.assertIn(
            "Contains unrealistic requirements for the advertised seniority",
            result.red_flags,
        )

    def test_detects_requested_seniority_levels(self) -> None:
        cases = (
            ("Software Engineering Intern", "Build Python services.", SeniorityLevel.INTERN),
            ("Junior Software Engineer", "Build Python services.", SeniorityLevel.JUNIOR),
            (
                "Software Engineer",
                "Requirements:\n- 4 years of experience in Python.",
                SeniorityLevel.MID_LEVEL,
            ),
            ("Senior Software Engineer", "Build Python services.", SeniorityLevel.SENIOR),
            ("Lead Software Engineer", "Build Python services.", SeniorityLevel.LEAD),
            ("Engineering Manager", "Build Python services.", SeniorityLevel.MANAGER),
            ("Software Engineer", "Build Python services.", SeniorityLevel.UNKNOWN),
        )
        for title, description, expected in cases:
            with self.subTest(title=title, expected=expected):
                result = self.analyzer.analyze(
                    JobDescriptionInput(raw_title=title, description_text=description)
                )
                self.assertEqual(result.seniority_level, expected)

    def test_future_openai_analyzer_remains_an_abstract_placeholder(self) -> None:
        self.assertTrue(isabstract(FutureOpenAIJobAnalyzer))
