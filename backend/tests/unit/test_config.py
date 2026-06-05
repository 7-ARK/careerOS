"""Tests for environment-backed configuration."""

import os
import unittest
from unittest.mock import patch

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    """Verify that settings are read from the process environment."""

    def test_from_env_reads_supported_variables(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "DATABASE_URL": "postgresql://localhost/careeros",
                "USE_LLM_RESUME_INTELLIGENCE": "true",
                "OPENAI_MODEL": "gpt-4.1-mini",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.database_url, "postgresql://localhost/careeros")
        self.assertTrue(settings.use_llm_resume_intelligence)
        self.assertEqual(settings.openai_model, "gpt-4.1-mini")

    def test_from_env_defaults_llm_resume_intelligence_to_false(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertFalse(settings.use_llm_resume_intelligence)
        self.assertEqual(settings.openai_model, "gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
