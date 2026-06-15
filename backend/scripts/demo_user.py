"""Shared demo account setup for local seed scripts."""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.repositories import UserRepository

DEMO_EMAIL = "demo@careeros.local"
DEMO_PASSWORD = "password123"


def get_or_create_demo_user(session: Session) -> User:
    """Create or reuse the local-only demo account."""
    users = UserRepository(session)
    existing = users.get_by_email(DEMO_EMAIL)
    if existing is not None:
        return existing
    user = users.create(
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="careerOS Demo",
    )
    session.commit()
    return user
