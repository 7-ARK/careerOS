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
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.database_url, "postgresql://localhost/careeros")


if __name__ == "__main__":
    unittest.main()
