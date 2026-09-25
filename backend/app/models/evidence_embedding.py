"""Durable pgvector storage for candidate evidence embeddings.

Dimension choice: the column is an unbounded ``vector``, not ``vector(N)``.
The default local provider (``feature-hash-v1``) emits 256 dimensions.
``OpenAIEmbeddingProvider`` calls ``text-embedding-3-small`` without a
``dimensions`` argument, so OpenAI returns its 1536-dimension default.
One fixed ``vector(N)`` column cannot store both widths. Each row records
``embedding_dimensions``, PostgreSQL checks ``vector_dims(embedding)`` against
that value, and search keeps exact cosine comparisons inside one width.
SQLite migrations store the same column as text so the existing CI schema
check can build; ``PgVectorStore`` rejects non-PostgreSQL dialects.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmbeddingVector(TypeDecorator[list[float]]):
    """Persist embeddings as pgvector on PostgreSQL and JSON text on SQLite."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> UserDefinedType[Any] | Text:
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return Vector()
        return dialect.type_descriptor(Text())

    def process_bind_param(
        self,
        value: list[float] | None,
        dialect: Any,
    ) -> list[float] | str | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [float(item) for item in value]
        if isinstance(value, str):
            loaded = json.loads(value)
            return [float(item) for item in loaded]
        return [float(item) for item in value]


class EvidenceEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One cached evidence embedding owned by a single candidate profile."""

    __tablename__ = "evidence_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "evidence_id",
            "embedding_model",
            "content_hash",
            name="uq_evidence_embeddings_cache_key",
        ),
        CheckConstraint(
            "embedding_dimensions > 0",
            name="embedding_dimensions_positive",
        ),
        Index(
            "ix_evidence_embeddings_profile_model_dims",
            "candidate_profile_id",
            "embedding_model",
            "embedding_dimensions",
        ),
    )

    evidence_id: Mapped[str] = mapped_column(String(250), nullable=False)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="candidate_profile")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
