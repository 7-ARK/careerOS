"""Transparent candidate-evidence chunking, embeddings, and hybrid retrieval.

Tests and CI use ``DeterministicHashEmbeddingProvider``. Live mode can select
``OpenAIEmbeddingProvider`` with ``RAG_EMBEDDING_PROVIDER=openai``. Hybrid
ranking stays lexical 0.7 / vector 0.3 and does not rerank.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from uuid import UUID

from app.core.config import Settings
from app.models import CandidateProfile
from app.schemas import CandidateEvidence, RetrievedCandidateEvidence

TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]+")
DEFAULT_EMBEDDING_DIMENSIONS = 256
DEFAULT_OPENAI_EMBEDDING_BATCH_SIZE = 64
OPENAI_EMBEDDING_MAX_BATCH_SIZE = 2048
OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def normalize_text(value: str) -> str:
    """Normalize text consistently for chunking, lexical matching, and embeddings."""
    normalized = value.casefold()
    replacements = {
        "apis": "api",
        "databases": "database",
        "workflows": "workflow",
        "technologies": "technology",
        "machine-learning": "machine learning",
        "human-in-the-loop": "human review",
        "human in the loop": "human review",
        "large language models": "large language model llm",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    tokens = [token.strip(".") for token in TOKEN_PATTERN.findall(normalized)]
    tokens = [token for token in tokens if token]
    aliases = {
        "github": ("git",),
        "langchain": ("llm",),
        "langgraph": ("llm",),
        "openai": ("llm",),
        "rag": ("llm",),
    }
    expanded = [token for value in tokens for token in (value, *aliases.get(value, ()))]
    return " ".join(expanded)


class EmbeddingProviderError(RuntimeError):
    """The embedding provider failed or returned a response that cannot be stored."""


@dataclass(frozen=True, slots=True)
class EmbeddingUsage:
    """Token accounting for one provider instance. Cost is computed by the caller."""

    prompt_tokens: int = 0
    requests: int = 0


class EmbeddingProvider(Protocol):
    """Provider-independent embedding boundary used by candidate retrieval."""

    @property
    def provider_name(self) -> str:
        """Return a safe provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the configured embedding model identifier."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed normalized texts in source order."""


class DeterministicHashEmbeddingProvider:
    """Create stable local feature-hash embeddings without credentials or network calls."""

    provider_name = "deterministic_local"
    model_name = "feature-hash-v1"

    def __init__(self, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> None:
        if dimensions < 32:
            raise ValueError("deterministic embedding dimensions must be at least 32")
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = normalize_text(text).split()
        features = [
            *tokens,
            *(
                f"{left}_{right}"
                for left, right in zip(tokens, tokens[1:], strict=False)
            ),
        ]
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector


class OpenAIEmbeddingProvider:
    """Live semantic embeddings. Constructing the provider does not call the network."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: int,
        dimensions: int | None = None,
        batch_size: int = DEFAULT_OPENAI_EMBEDDING_BATCH_SIZE,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("OpenAI embedding provider requires an API key")
        if timeout_seconds < 1:
            raise ValueError("OpenAI embedding timeout must be at least 1 second")
        if not model_name.strip():
            raise ValueError("OpenAI embedding model name must not be empty")
        if batch_size < 1 or batch_size > OPENAI_EMBEDDING_MAX_BATCH_SIZE:
            raise ValueError(
                "OpenAI embedding batch size must be between 1 and "
                f"{OPENAI_EMBEDDING_MAX_BATCH_SIZE}"
            )
        if dimensions is not None and dimensions < 1:
            raise ValueError("OpenAI embedding dimensions must be a positive integer")
        self._api_key = api_key.strip()
        self.model_name = model_name.strip()
        self.timeout_seconds = timeout_seconds
        self.batch_size = batch_size
        self._dimensions_override = dimensions
        self.dimensions = (
            dimensions
            if dimensions is not None
            else OPENAI_EMBEDDING_DIMENSIONS.get(self.model_name)
        )
        self.usage = EmbeddingUsage()

    def __repr__(self) -> str:
        return (
            "OpenAIEmbeddingProvider("
            f"model_name={self.model_name!r}, dimensions={self.dimensions})"
        )

    def contains_secret(self, value: str) -> bool:
        """Return whether a stored or logged value includes the API key."""
        return bool(self._api_key) and self._api_key in value

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in source order, in batches, without logging the API key."""
        if not texts:
            return []
        client = self._client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(client, texts[start : start + self.batch_size]))
        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"OpenAI embeddings returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        return vectors

    def _client(self) -> object:
        from openai import OpenAI

        return OpenAI(
            api_key=self._api_key,
            timeout=float(self.timeout_seconds),
            max_retries=1,
        )

    def _embed_batch(self, client: object, texts: list[str]) -> list[list[float]]:
        kwargs: dict[str, object] = {
            "model": self.model_name,
            "input": texts,
            "timeout": float(self.timeout_seconds),
        }
        if self._dimensions_override is not None:
            kwargs["dimensions"] = self._dimensions_override
        try:
            response = client.embeddings.create(**kwargs)  # type: ignore[attr-defined]
        except Exception as exc:
            detail = _redact_secret(f"{type(exc).__name__}: {exc}", self._api_key)
            raise EmbeddingProviderError(
                f"OpenAI embeddings request failed for model {self.model_name!r}: {detail}"
            ) from None
        vectors = self._vectors_from_response(response, expected_count=len(texts))
        self._record_usage(response)
        return vectors

    def _vectors_from_response(
        self,
        response: object,
        *,
        expected_count: int,
    ) -> list[list[float]]:
        data = getattr(response, "data", None)
        if not data:
            raise EmbeddingProviderError(
                f"OpenAI embeddings returned no vectors for model {self.model_name!r}"
            )
        if len(data) != expected_count:
            raise EmbeddingProviderError(
                f"OpenAI embeddings returned {len(data)} vectors for {expected_count} inputs"
            )
        try:
            ordered = sorted(data, key=lambda item: item.index)
            indexes = [item.index for item in ordered]
        except (AttributeError, TypeError):
            raise EmbeddingProviderError(
                "OpenAI embeddings response did not include vector indexes"
            ) from None
        if indexes != list(range(expected_count)):
            raise EmbeddingProviderError(
                "OpenAI embeddings response did not include every input index"
            )
        return [self._validate_vector(item.embedding) for item in ordered]

    def _validate_vector(self, values: object) -> list[float]:
        try:
            raw = list(values)  # type: ignore[arg-type]
        except TypeError:
            raise EmbeddingProviderError(
                "OpenAI embeddings returned a non-iterable vector"
            ) from None
        cleaned: list[float] = []
        for value in raw:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise EmbeddingProviderError(
                    "OpenAI embeddings returned a non-numeric value"
                ) from None
            if not math.isfinite(number):
                raise EmbeddingProviderError("OpenAI embeddings returned a non-finite value")
            cleaned.append(number)
        if not cleaned:
            raise EmbeddingProviderError("OpenAI embeddings returned an empty vector")
        if self.dimensions is None:
            self.dimensions = len(cleaned)
        elif len(cleaned) != self.dimensions:
            raise EmbeddingProviderError(
                f"OpenAI embeddings returned {len(cleaned)} dimensions for model "
                f"{self.model_name!r}; expected {self.dimensions}"
            )
        return cleaned

    def _record_usage(self, response: object) -> None:
        usage = getattr(response, "usage", None)
        tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        self.usage = EmbeddingUsage(
            prompt_tokens=self.usage.prompt_tokens + tokens,
            requests=self.usage.requests + 1,
        )


def _redact_secret(message: str, secret: str) -> str:
    """Remove an API key from a provider error before it can reach logs."""
    if secret and secret in message:
        return message.replace(secret, "[redacted]")
    return message


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Select the configured provider.

    ``deterministic`` is the free local mode. ``openai`` requires ``OPENAI_API_KEY``
    and does not silently switch back to local embeddings. Preview mode sets the
    provider to deterministic before this function runs.
    """
    settings = settings or Settings.from_env()
    if settings.rag_embedding_provider not in {"deterministic", "openai"}:
        raise ValueError("RAG_EMBEDDING_PROVIDER must be 'deterministic' or 'openai'")
    if settings.rag_embedding_provider == "deterministic":
        return DeterministicHashEmbeddingProvider()
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise ValueError(
            "RAG_EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY. "
            "Set the key, or use RAG_EMBEDDING_PROVIDER=deterministic for local embeddings."
        )
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model_name=settings.rag_embedding_model,
        timeout_seconds=settings.provider_timeout_seconds,
        dimensions=settings.rag_embedding_dimensions,
    )


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One evidence chunk and its provider-independent vector."""

    evidence: CandidateEvidence
    vector: list[float]


class EvidenceVectorIndex(Protocol):
    """Candidate-scoped vector source used before hybrid ranking.

    ``search`` is intentionally not part of this contract. ``PgVectorStore.search``
    is cosine-only; requirement ranking stays in ``rank_evidence``.
    """

    def sync(
        self,
        candidate_profile_id: UUID,
        evidence: list[CandidateEvidence],
    ) -> list[VectorRecord]:
        """Return this candidate's current evidence vectors in input order."""


class LocalVectorStore:
    """Single-process vector index rebuilt from the durable candidate source of truth."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self._records: list[VectorRecord] = []

    def index(self, evidence: list[CandidateEvidence]) -> None:
        vectors = self.provider.embed([item.text for item in evidence]) if evidence else []
        if len(vectors) != len(evidence):
            raise ValueError("embedding provider returned an unexpected vector count")
        self._records = [
            VectorRecord(evidence=item, vector=vector)
            for item, vector in zip(evidence, vectors, strict=True)
        ]

    def sync(
        self,
        candidate_profile_id: UUID,
        evidence: list[CandidateEvidence],
    ) -> list[VectorRecord]:
        """Rebuild the in-memory index for one candidate and return its vectors."""
        if not isinstance(candidate_profile_id, UUID):
            raise TypeError("candidate_profile_id is required")
        self.index(evidence)
        return list(self._records)

    def search(
        self,
        query: str,
        *,
        top_k: int,
        categories: set[str] | None = None,
    ) -> list[RetrievedCandidateEvidence]:
        return rank_evidence(
            self.provider,
            self._records,
            query,
            top_k=top_k,
            categories=categories,
        )


def rank_evidence(
    provider: EmbeddingProvider,
    records: list[VectorRecord],
    query: str,
    *,
    top_k: int,
    categories: set[str] | None = None,
) -> list[RetrievedCandidateEvidence]:
    """Rank evidence with the existing lexical gate and 0.7/0.3 hybrid score."""
    query_vector = provider.embed([query])[0]
    query_tokens = set(normalize_text(query).split())
    matches: list[tuple[Decimal, RetrievedCandidateEvidence]] = []
    for record in records:
        if categories and record.evidence.category not in categories:
            continue
        evidence_tokens = set(normalize_text(record.evidence.text).split())
        lexical = (
            Decimal(len(query_tokens & evidence_tokens)) / Decimal(len(query_tokens))
            if query_tokens
            else Decimal("0")
        )
        cosine = max(0.0, _cosine_similarity(query_vector, record.vector))
        vector = Decimal(str(cosine))
        combined = min(Decimal("1"), lexical * Decimal("0.7") + vector * Decimal("0.3"))
        retrieved = RetrievedCandidateEvidence(
            **record.evidence.model_dump(),
            retrieval_score=_score(combined),
            lexical_score=_score(lexical),
            vector_score=_score(vector),
            why_retrieved=(
                "Exact or overlapping requirement terms were found in verified evidence."
                if lexical > 0
                else (
                    "The deterministic embedding ranked this verified evidence as related."
                    if provider.provider_name == "deterministic_local"
                    else "The embedding ranked this verified evidence as related."
                )
            ),
        )
        matches.append((combined, retrieved))
    matches.sort(
        key=lambda item: (
            -item[0],
            -item[1].lexical_score,
            item[1].evidence_id,
        )
    )
    return [item for _, item in matches[:top_k]]


def build_candidate_evidence_retriever(
    session: object | None = None,
    *,
    settings: Settings | None = None,
    provider: EmbeddingProvider | None = None,
) -> CandidateEvidenceRetriever:
    """Select the configured vector index and keep hybrid ranking in the retriever."""
    settings = settings or Settings.from_env()
    provider = provider or build_embedding_provider(settings)
    choice = settings.rag_vector_store
    if choice == "local":
        return CandidateEvidenceRetriever(provider)
    if choice == "pgvector":
        if session is None:
            raise RuntimeError("RAG_VECTOR_STORE=pgvector requires a database session")
        from sqlalchemy.orm import Session

        from app.features.resume_intelligence.pgvector_store import PgVectorStore

        if not isinstance(session, Session):
            raise TypeError("RAG_VECTOR_STORE=pgvector requires a SQLAlchemy session")
        return CandidateEvidenceRetriever(provider, vector_index=PgVectorStore(session, provider))
    raise ValueError("RAG_VECTOR_STORE must be 'local' or 'pgvector'")


class CandidateEvidenceRetriever:
    """Build and query stable verified evidence chunks for one candidate profile."""

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        vector_index: EvidenceVectorIndex | None = None,
    ) -> None:
        self.provider = provider or build_embedding_provider()
        self.vector_index = vector_index or LocalVectorStore(self.provider)

    def collect(self, candidate: CandidateProfile) -> list[CandidateEvidence]:
        """Convert durable candidate rows into stable, privacy-conscious evidence chunks."""
        evidence: list[CandidateEvidence] = []
        profile_text = " ".join(
            value for value in (candidate.headline, candidate.summary, candidate.location) if value
        )
        if profile_text:
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"profile-{candidate.id}-summary",
                    source_id=candidate.id,
                    category="profile",
                    text=profile_text,
                    metadata={"label": candidate.headline or "Candidate profile summary"},
                )
            )
        for skill in candidate.skills:
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"skill-{skill.id}",
                    source_id=skill.id,
                    category="skill",
                    text=(
                        f"{skill.name}. Category: {skill.category}. "
                        f"Candidate-reported experience: {skill.years_of_experience} years."
                    ),
                    metadata={"label": skill.name},
                )
            )
        for project in candidate.projects:
            project_text = " ".join(
                part
                for part in (
                    project.title,
                    project.description,
                    "Technologies: " + ", ".join(project.technologies)
                    if project.technologies
                    else "",
                    "Verified outcomes: " + "; ".join(project.outcomes)
                    if project.outcomes
                    else "",
                )
                if part
            )
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"project-{project.id}",
                    source_id=project.id,
                    category="project",
                    text=project_text,
                    metadata={
                        "label": project.title,
                        "github_url": project.github_url,
                        "portfolio_url": project.portfolio_url,
                    },
                )
            )
        for experience in candidate.work_experiences:
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"experience-{experience.id}",
                    source_id=experience.id,
                    category="experience",
                    text=" ".join(
                        part
                        for part in (
                            f"{experience.job_title} at {experience.company}.",
                            experience.description or "",
                            "Verified achievements: " + "; ".join(experience.achievements)
                            if experience.achievements
                            else "",
                        )
                        if part
                    ),
                    metadata={"label": f"{experience.job_title} at {experience.company}"},
                )
            )
        for education in candidate.education:
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"education-{education.id}",
                    source_id=education.id,
                    category="education",
                    text=" ".join(
                        part
                        for part in (
                            education.degree,
                            education.field_of_study or "",
                            f"at {education.institution}",
                            education.description or "",
                        )
                        if part
                    ),
                    metadata={"label": f"{education.degree} at {education.institution}"},
                )
            )
        for certification in candidate.certifications:
            evidence.append(
                CandidateEvidence(
                    evidence_id=f"certification-{certification.id}",
                    source_id=certification.id,
                    category="certification",
                    text=(
                        f"{certification.name} issued by "
                        f"{certification.issuing_organization}."
                    ),
                    metadata={"label": certification.name},
                )
            )
        return evidence

    def retrieve(
        self,
        candidate: CandidateProfile,
        query: str,
        *,
        top_k: int = 3,
        categories: set[str] | None = None,
    ) -> list[RetrievedCandidateEvidence]:
        """Retrieve top-k evidence while preserving transparent score components."""
        records = self.vector_index.sync(candidate.id, self.collect(candidate))
        return rank_evidence(
            self.provider,
            records,
            query,
            top_k=top_k,
            categories=categories,
        )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding vectors must use the same dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), value)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
