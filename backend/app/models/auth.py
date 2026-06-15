"""Minimal user accounts for private careerOS data."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.knowledge_base import CandidateProfile


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Own candidate profiles and authenticate with email and password."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))

    candidate_profiles: Mapped[list["CandidateProfile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
