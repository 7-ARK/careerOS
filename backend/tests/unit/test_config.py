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
                "JWT_SECRET_KEY": "test-secret",
                "JWT_ALGORITHM": "HS256",
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.database_url, "postgresql://localhost/careeros")
        self.assertTrue(settings.use_llm_resume_intelligence)
        self.assertEqual(settings.openai_model, "gpt-4.1-mini")
        self.assertEqual(settings.jwt_secret_key, "test-secret")
        self.assertEqual(settings.jwt_algorithm, "HS256")
        self.assertEqual(settings.jwt_access_token_expire_minutes, 60)
        self.assertEqual(settings.rag_vector_store, "local")
        self.assertEqual(settings.rag_embedding_provider, "deterministic")
        self.assertEqual(settings.rag_embedding_model, "text-embedding-3-small")
        self.assertIsNone(settings.rag_embedding_dimensions)

    def test_from_env_defaults_llm_resume_intelligence_to_false(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertFalse(settings.use_llm_resume_intelligence)
        self.assertEqual(settings.openai_model, "gpt-4.1-mini")
        self.assertEqual(settings.jwt_algorithm, "HS256")
        self.assertEqual(settings.jwt_access_token_expire_minutes, 1440)
        self.assertEqual(settings.rag_vector_store, "local")
        self.assertEqual(settings.rag_embedding_provider, "deterministic")
        self.assertIsNone(settings.rag_embedding_dimensions)

    def test_embedding_provider_accepts_openai_and_rejects_unknown_values(self) -> None:
        with patch.dict(
            os.environ,
            {"RAG_EMBEDDING_PROVIDER": "OpenAI", "OPENAI_API_KEY": "test-key"},
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.rag_embedding_provider, "openai")
        self.assertEqual(settings.openai_api_key, "test-key")

        with patch.dict(os.environ, {"RAG_EMBEDDING_PROVIDER": "voyage"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

        with patch.dict(os.environ, {"RAG_EMBEDDING_MODEL": "   "}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_embedding_dimensions_must_be_a_positive_integer(self) -> None:
        with patch.dict(os.environ, {"RAG_EMBEDDING_DIMENSIONS": "1536"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.rag_embedding_dimensions, 1536)

        with patch.dict(os.environ, {"RAG_EMBEDDING_DIMENSIONS": "0"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

        with patch.dict(os.environ, {"RAG_EMBEDDING_DIMENSIONS": "wide"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_preview_mode_forces_provider_free_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CAREEROS_PREVIEW_MODE": "true",
                "OPENAI_API_KEY": "must-not-be-used",
                "USE_LLM_RESUME_INTELLIGENCE": "true",
                "RAG_EMBEDDING_PROVIDER": "openai",
                "RAG_VECTOR_STORE": "pgvector",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertTrue(settings.preview_mode)
        self.assertIsNone(settings.openai_api_key)
        self.assertFalse(settings.use_llm_resume_intelligence)
        self.assertEqual(settings.rag_embedding_provider, "deterministic")
        self.assertEqual(settings.rag_vector_store, "local")

    def test_vector_store_accepts_pgvector_and_rejects_unknown_backends(self) -> None:
        with patch.dict(os.environ, {"RAG_VECTOR_STORE": "pgvector"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.rag_vector_store, "pgvector")

        with patch.dict(os.environ, {"RAG_VECTOR_STORE": "chroma"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
