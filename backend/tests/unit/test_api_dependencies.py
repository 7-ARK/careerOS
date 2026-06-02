"""Unit tests for lazy FastAPI database dependencies."""

import os
import unittest
from unittest.mock import patch

from app.api.dependencies import get_session_factory


class ApiDependencyTests(unittest.TestCase):
    """Verify that API sessions are created lazily from `DATABASE_URL`."""

    def tearDown(self) -> None:
        get_session_factory.cache_clear()

    def test_session_factory_uses_database_url(self) -> None:
        get_session_factory.cache_clear()
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite+pysqlite:///:memory:"}, clear=True):
            factory = get_session_factory()

        engine = factory.kw["bind"]
        self.assertEqual(str(engine.url), "sqlite+pysqlite:///:memory:")
        engine.dispose()

    def test_session_factory_requires_database_url(self) -> None:
        get_session_factory.cache_clear()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            get_session_factory()


if __name__ == "__main__":
    unittest.main()
