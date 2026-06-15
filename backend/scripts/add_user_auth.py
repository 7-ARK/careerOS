"""Add minimal user ownership to an existing careerOS database."""

from uuid import uuid4

from sqlalchemy import inspect, text

from app.core.config import Settings
from app.core.security import hash_password
from app.db import Base, create_database_engine
from scripts.demo_user import DEMO_EMAIL, DEMO_PASSWORD


def main() -> None:
    """Create auth storage and assign legacy profiles to the demo user."""
    database_url = Settings.from_env().database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is required. Set it before running this migration.")

    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["users"]])
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("candidate_profiles")}

    with engine.begin() as connection:
        if "user_id" not in columns:
            connection.execute(text("ALTER TABLE candidate_profiles ADD COLUMN user_id UUID"))
        user_id = connection.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": DEMO_EMAIL},
        ).scalar_one_or_none()
        if user_id is None:
            user_id = uuid4()
            user_id = connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, full_name) "
                    "VALUES (:id, :email, :password_hash, :full_name) "
                    "RETURNING id"
                ),
                {
                    "id": user_id,
                    "email": DEMO_EMAIL,
                    "password_hash": hash_password(DEMO_PASSWORD),
                    "full_name": "careerOS Demo",
                },
            ).scalar_one()
        connection.execute(
            text("UPDATE candidate_profiles SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": user_id},
        )
        connection.execute(text("ALTER TABLE candidate_profiles ALTER COLUMN user_id SET NOT NULL"))

        inspector = inspect(connection)
        foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("candidate_profiles")}
        if "fk_candidate_profiles_user_id_users" not in foreign_keys:
            connection.execute(
                text(
                    "ALTER TABLE candidate_profiles "
                    "ADD CONSTRAINT fk_candidate_profiles_user_id_users "
                    "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                )
            )
        indexes = {index["name"] for index in inspector.get_indexes("candidate_profiles")}
        if "ix_candidate_profiles_user_id" not in indexes:
            connection.execute(
                text("CREATE INDEX ix_candidate_profiles_user_id ON candidate_profiles (user_id)")
            )

    print("user authentication schema is ready")
    print(f"demo_email={DEMO_EMAIL}")
    print(f"demo_password={DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
