"""Environment-backed application configuration."""

from dataclasses import dataclass
from os import environ

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    openai_api_key: str | None
    database_url: str | None
    use_llm_resume_intelligence: bool
    openai_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment."""
        return cls(
            openai_api_key=environ.get("OPENAI_API_KEY"),
            database_url=environ.get("DATABASE_URL"),
            use_llm_resume_intelligence=_env_bool("USE_LLM_RESUME_INTELLIGENCE"),
            openai_model=environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        )


def _env_bool(name: str) -> bool:
    """Read a conservative boolean flag from the environment."""
    return environ.get(name, "false").strip().casefold() in {"1", "true", "yes", "on"}
