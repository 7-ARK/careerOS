"""Add profile-level GitHub URLs to an existing careerOS database."""

from sqlalchemy import inspect, text

from app.core.config import Settings
from app.db import create_database_engine


def main() -> None:
    """Apply the idempotent schema change required by candidate profile management."""
    database_url = Settings.from_env().database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is required. Set it before running this migration.")

    engine = create_database_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("candidate_profiles")}
    if "github_url" in columns:
        print("candidate_profiles.github_url already exists")
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE candidate_profiles ADD COLUMN github_url VARCHAR(500)")
        )
    print("added candidate_profiles.github_url")


if __name__ == "__main__":
    main()
