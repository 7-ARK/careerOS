"""Unit tests for safe visible-text job URL extraction."""

import unittest
from decimal import Decimal

from app.features.job_url_extraction.extractors import PlaywrightJobExtractor
from app.models.enums import SourcePlatform


class PlaywrightJobExtractorUnitTests(unittest.TestCase):
    """Verify domain detection, cleanup, inference, and safe-stop behavior."""

    def setUp(self) -> None:
        self.extractor = PlaywrightJobExtractor()

    def test_detects_supported_and_unknown_platforms(self) -> None:
        self.assertEqual(
            self.extractor.detect_platform("https://www.linkedin.com/jobs/view/123"),
            SourcePlatform.LINKEDIN,
        )
        self.assertEqual(
            self.extractor.detect_platform("https://pk.indeed.com/viewjob?jk=123"),
            SourcePlatform.INDEED,
        )
        self.assertEqual(
            self.extractor.detect_platform("https://www.glassdoor.com/job-listing/123"),
            SourcePlatform.GLASSDOOR,
        )
        self.assertEqual(
            self.extractor.detect_platform("https://careers.example.com/jobs/123"),
            SourcePlatform.UNKNOWN,
        )

    def test_cleans_navigation_noise_and_duplicate_lines(self) -> None:
        cleaned = self.extractor.clean_visible_text(
            "Home\nJobs\nBackend Engineer\nBackend Engineer\nPlatform Labs\nPrivacy\n"
        )

        self.assertEqual(cleaned, "Backend Engineer\nPlatform Labs")

    def test_generic_inference_returns_pipeline_ready_fields(self) -> None:
        result = self.extractor.extract_from_visible_text(
            job_url="https://careers.example.com/jobs/backend",
            page_title="Backend Engineer - Platform Labs",
            visible_text="""
            Home
            Backend Engineer
            Platform Labs
            Remote
            Full-time
            We are hiring a backend engineer to build reliable Python APIs,
            FastAPI services, PostgreSQL integrations, and automation workflows.
            """,
        )

        self.assertEqual(result.detected_platform, SourcePlatform.UNKNOWN)
        self.assertEqual(result.raw_title, "Backend Engineer")
        self.assertEqual(result.company_name, "Platform Labs")
        self.assertEqual(result.location, "Remote")
        self.assertEqual(result.employment_type, "full_time")
        self.assertEqual(result.workplace_type, "remote")
        self.assertTrue(result.pipeline_ready)
        self.assertGreater(result.extraction_confidence, Decimal("0.5"))

    def test_login_and_captcha_pages_stop_safely(self) -> None:
        for text in (
            "Sign in to continue to this job posting.",
            "Please complete the CAPTCHA to verify you are human.",
        ):
            with self.subTest(text=text):
                result = self.extractor.extract_from_visible_text(
                    job_url="https://www.linkedin.com/jobs/view/123",
                    visible_text=text,
                )

                self.assertFalse(result.pipeline_ready)
                self.assertEqual(result.extraction_confidence, Decimal("0"))
                self.assertTrue(
                    any("manual import fallback" in item for item in result.extraction_warnings)
                )


if __name__ == "__main__":
    unittest.main()
