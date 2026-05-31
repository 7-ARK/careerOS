"""Tests for application health reporting."""

import unittest

from app.api.routes.health import get_health_status


class HealthStatusTests(unittest.TestCase):
    """Verify the framework-agnostic health payload."""

    def test_health_status_is_ok(self) -> None:
        self.assertEqual(
            get_health_status(),
            {
                "name": "careerOS",
                "version": "0.1.0",
                "status": "ok",
            },
        )


if __name__ == "__main__":
    unittest.main()
