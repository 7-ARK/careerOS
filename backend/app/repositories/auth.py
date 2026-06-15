"""Persistence operations for user accounts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.knowledge_base import Repository


class UserRepository(Repository[User]):
    """Create and retrieve minimal user accounts."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_email(self, email: str) -> User | None:
        """Find one user by normalized email address."""
        return self.session.scalar(select(User).where(User.email == email.casefold()))
