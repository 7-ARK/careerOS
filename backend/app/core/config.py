"""Environment-backed application configuration."""

from dataclasses import dataclass
from os import environ

from dotenv import load_dotenv

PREVIEW_MODE_ENABLED = environ.get("CAREEROS_PREVIEW_MODE", "false").strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}
if not PREVIEW_MODE_ENABLED:
    load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    openai_api_key: str | None
    database_url: str | None
    preview_mode: bool
    use_llm_resume_intelligence: bool
    openai_model: str
    rag_embedding_provider: str
    rag_embedding_model: str
    provider_timeout_seconds: int
    cors_origins: tuple[str, ...]
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment."""
        preview_mode = _env_bool("CAREEROS_PREVIEW_MODE")
        return cls(
            openai_api_key=None if preview_mode else environ.get("OPENAI_API_KEY"),
            database_url=environ.get("DATABASE_URL"),
            preview_mode=preview_mode,
            use_llm_resume_intelligence=(
                False if preview_mode else _env_bool("USE_LLM_RESUME_INTELLIGENCE")
            ),
            openai_model=environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            rag_embedding_provider=(
                "deterministic"
                if preview_mode
                else environ.get("RAG_EMBEDDING_PROVIDER", "deterministic").strip().casefold()
            ),
            rag_embedding_model=environ.get(
                "RAG_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            provider_timeout_seconds=int(environ.get("PROVIDER_TIMEOUT_SECONDS", "30")),
            cors_origins=tuple(
                origin.strip()
                for origin in environ.get(
                    "CORS_ORIGINS",
                    "http://localhost:3000,http://127.0.0.1:3000",
                ).split(",")
                if origin.strip()
            ),
            jwt_secret_key=environ.get(
                "JWT_SECRET_KEY",
                "careeros-local-development-secret-change-me",
            ),
            jwt_algorithm=environ.get("JWT_ALGORITHM", "HS256"),
            jwt_access_token_expire_minutes=int(
                environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
            ),
        )


def _env_bool(name: str) -> bool:
    """Read a conservative boolean flag from the environment."""
    return environ.get(name, "false").strip().casefold() in {"1", "true", "yes", "on"}
