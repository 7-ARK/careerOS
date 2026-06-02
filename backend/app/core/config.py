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

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment."""
        return cls(
            openai_api_key=environ.get("OPENAI_API_KEY"),
            database_url=environ.get("DATABASE_URL"),
        )
