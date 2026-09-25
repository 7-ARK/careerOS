"""PostgreSQL pgvector store for candidate evidence embeddings.

``search`` uses exact cosine distance (``<=>``) with no ANN index. The CareerOS
retriever does not rank with that method. It calls ``sync`` for candidate-scoped
vectors and keeps lexical gates plus hybrid scoring in ``rank_evidence``.
Every read and write filters ``candidate_profile_id``. Cache identity is
``(evidence_id, embedding_model, content_hash)``: unchanged text is not
re-embedded.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import literal_column

from app.features.resume_intelligence.retrieval import EmbeddingProvider, VectorRecord, _score
from app.models.evidence_embedding import EvidenceEmbedding
from app.schemas import CandidateEvidence, RetrievedCandidateEvidence

_WHY_RETRIEVED = "Exact cosine similarity over the persisted evidence embedding."


@dataclass(frozen=True, slots=True)
class EmbeddingIndexResult:
    """How many embeddings were generated versus reused from cache."""

    embedded: int
    reused: int


def evidence_content_hash(value: str) -> str:
    """Hash the exact evidence text that would be sent to the provider."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PgVectorStore:
    """Persist and search evidence embeddings for one candidate at a time."""

    def __init__(self, session: Session, provider: EmbeddingProvider) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            raise RuntimeError("PgVectorStore requires PostgreSQL with the pgvector extension")
        installed = session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        if installed is None:
            raise RuntimeError("pgvector extension is not installed on this database")
        self.session = session
        self.provider = provider

    def index(
        self,
        candidate_profile_id: UUID,
        evidence: list[CandidateEvidence],
    ) -> EmbeddingIndexResult:
        """Insert or reuse embeddings for one candidate.

        Rows whose text and model are unchanged keep their stored vector.
        Rows that no longer match the supplied evidence are deleted for this
        candidate and model only.
        """
        model_name = self.provider.model_name
        expected_dimensions = _provider_dimensions(self.provider)
        evidence_ids = [item.evidence_id for item in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique within an index batch")
        hashes = {item.evidence_id: evidence_content_hash(item.text) for item in evidence}

        scope = [EvidenceEmbedding.candidate_profile_id == candidate_profile_id]
        if hashes:
            scope.append(EvidenceEmbedding.evidence_id.in_(list(hashes)))
        rows = list(
            self.session.scalars(
                select(EvidenceEmbedding).where(
                    EvidenceEmbedding.embedding_model == model_name,
                    or_(*scope),
                )
            )
        )
        by_key = {(row.evidence_id, row.content_hash): row for row in rows}

        reused = 0
        pending: list[CandidateEvidence] = []
        kept: set[tuple[str, str]] = set()
        for item in evidence:
            key = (item.evidence_id, hashes[item.evidence_id])
            row = by_key.get(key)
            if row is not None and row.candidate_profile_id != candidate_profile_id:
                raise ValueError(
                    f"evidence_id {item.evidence_id!r} is already stored for a different candidate"
                )
            if row is not None and _dimensions_match(row.embedding_dimensions, expected_dimensions):
                _copy_evidence(row, candidate_profile_id, item)
                reused += 1
                kept.add(key)
                continue
            pending.append(item)

        prepared: list[tuple[CandidateEvidence, list[float]]] = []
        if pending:
            vectors = self.provider.embed([item.text for item in pending])
            if len(vectors) != len(pending):
                raise ValueError("embedding provider returned an unexpected vector count")
            for item, vector in zip(pending, vectors, strict=True):
                cleaned = _validate_vector(list(vector))
                if expected_dimensions is not None and len(cleaned) != expected_dimensions:
                    raise ValueError(
                        "embedding provider returned a vector whose length does not match "
                        "its configured dimensions"
                    )
                prepared.append((item, cleaned))

        for item, _cleaned in prepared:
            key = (item.evidence_id, hashes[item.evidence_id])
            stale = by_key.get(key)
            if stale is not None:
                # Same cache key can be replaced when the stored width no longer matches.
                # Delete before insert so the unique key is free.
                self.session.delete(stale)
            kept.add(key)

        for row in rows:
            if row.candidate_profile_id != candidate_profile_id:
                continue
            if (row.evidence_id, row.content_hash) not in kept:
                self.session.delete(row)
        self.session.flush()

        for item, cleaned in prepared:
            content_hash = hashes[item.evidence_id]
            self.session.add(
                EvidenceEmbedding(
                    evidence_id=item.evidence_id,
                    candidate_profile_id=candidate_profile_id,
                    source_id=item.source_id,
                    category=item.category,
                    source=item.source,
                    text=item.text,
                    evidence_metadata=dict(item.metadata),
                    embedding=cleaned,
                    embedding_dimensions=len(cleaned),
                    embedding_model=model_name,
                    content_hash=content_hash,
                )
            )
        if prepared:
            self.session.flush()
        return EmbeddingIndexResult(embedded=len(prepared), reused=reused)

    def sync(
        self,
        candidate_profile_id: UUID,
        evidence: list[CandidateEvidence],
    ) -> list[VectorRecord]:
        """Index one candidate's current evidence and return those stored vectors."""
        self.index(candidate_profile_id, evidence)
        return self.load_vectors(candidate_profile_id, evidence)

    def load_vectors(
        self,
        candidate_profile_id: UUID,
        evidence: list[CandidateEvidence],
    ) -> list[VectorRecord]:
        """Read stored vectors for one candidate without ranking them."""
        if not isinstance(candidate_profile_id, UUID):
            raise TypeError("candidate_profile_id is required")
        if not evidence:
            return []
        wanted = {item.evidence_id: evidence_content_hash(item.text) for item in evidence}
        rows = list(
            self.session.scalars(
                select(EvidenceEmbedding).where(
                    EvidenceEmbedding.candidate_profile_id == candidate_profile_id,
                    EvidenceEmbedding.embedding_model == self.provider.model_name,
                    EvidenceEmbedding.evidence_id.in_(list(wanted)),
                )
            )
        )
        by_key = {(row.evidence_id, row.content_hash): row for row in rows}
        loaded: list[VectorRecord] = []
        for item in evidence:
            row = by_key.get((item.evidence_id, wanted[item.evidence_id]))
            if row is None:
                raise RuntimeError(
                    f"evidence_id {item.evidence_id!r} has no embedding for this candidate"
                )
            loaded.append(VectorRecord(evidence=item, vector=list(row.embedding)))
        return loaded

    def search(
        self,
        query: str,
        *,
        candidate_profile_id: UUID,
        top_k: int,
        categories: set[str] | None = None,
        query_embedding: Sequence[float] | None = None,
    ) -> list[RetrievedCandidateEvidence]:
        """Return the top-k evidence rows for this candidate by exact cosine similarity."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if query_embedding is None:
            vectors = self.provider.embed([query])
            if len(vectors) != 1:
                raise ValueError("embedding provider returned an unexpected vector count")
            query_vector = _validate_vector(list(vectors[0]))
        else:
            query_vector = _validate_vector(list(query_embedding))

        distance_sql = (
            "(evidence_embeddings.embedding <=> "
            f"'{_vector_literal(query_vector)}'::vector)"
        )
        distance = literal_column(distance_sql).label("cosine_distance")
        statement = select(EvidenceEmbedding, distance).where(
            EvidenceEmbedding.candidate_profile_id == candidate_profile_id,
            EvidenceEmbedding.embedding_model == self.provider.model_name,
            EvidenceEmbedding.embedding_dimensions == len(query_vector),
        )
        if categories:
            statement = statement.where(EvidenceEmbedding.category.in_(sorted(categories)))
        statement = statement.order_by(
            literal_column(distance_sql),
            EvidenceEmbedding.evidence_id,
        ).limit(top_k)

        matches: list[RetrievedCandidateEvidence] = []
        for row, cosine_distance in self.session.execute(statement):
            similarity = 1.0 - float(cosine_distance)
            vector_score = _score(Decimal(str(similarity)))
            matches.append(
                RetrievedCandidateEvidence(
                    evidence_id=row.evidence_id,
                    source_id=row.source_id,
                    category=row.category,
                    source="candidate_profile",
                    text=row.text,
                    verified=True,
                    metadata=dict(row.evidence_metadata or {}),
                    retrieval_score=vector_score,
                    lexical_score=_score(Decimal("0")),
                    vector_score=vector_score,
                    why_retrieved=_WHY_RETRIEVED,
                )
            )
        return matches


def _provider_dimensions(provider: EmbeddingProvider) -> int | None:
    dimensions = getattr(provider, "dimensions", None)
    if dimensions is None:
        return None
    if not isinstance(dimensions, int) or isinstance(dimensions, bool) or dimensions < 1:
        raise ValueError("embedding provider dimensions must be a positive integer")
    return dimensions


def _dimensions_match(stored: int, expected: int | None) -> bool:
    return expected is None or stored == expected


def _copy_evidence(
    row: EvidenceEmbedding,
    candidate_profile_id: UUID,
    evidence: CandidateEvidence,
) -> None:
    row.candidate_profile_id = candidate_profile_id
    row.source_id = evidence.source_id
    row.category = evidence.category
    row.source = evidence.source
    row.text = evidence.text
    row.evidence_metadata = dict(evidence.metadata)


def _validate_vector(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("embedding must contain at least one dimension")
    cleaned: list[float] = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("embedding values must be finite")
        cleaned.append(number)
    return cleaned


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"
