"""Transparent candidate-evidence chunking, embeddings, and local vector retrieval."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.core.config import Settings
from app.models import CandidateProfile
from app.schemas import CandidateEvidence, RetrievedCandidateEvidence

TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]+")
DEFAULT_EMBEDDING_DIMENSIONS = 256


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
    """Optional real embedding provider enabled only by explicit environment configuration."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model_name: str, timeout_seconds: int) -> None:
        if not api_key:
            raise ValueError("OpenAI embedding provider requires an API key")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, timeout=float(self.timeout_seconds), max_retries=1)
        response = client.embeddings.create(model=self.model_name, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Resolve the configured provider and fall back locally when credentials are absent."""
    settings = settings or Settings.from_env()
    if settings.rag_embedding_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model_name=settings.rag_embedding_model,
            timeout_seconds=settings.provider_timeout_seconds,
        )
    return DeterministicHashEmbeddingProvider()


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One evidence chunk and its provider-independent vector."""

    evidence: CandidateEvidence
    vector: list[float]


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

    def search(
        self,
        query: str,
        *,
        top_k: int,
        categories: set[str] | None = None,
    ) -> list[RetrievedCandidateEvidence]:
        query_vector = self.provider.embed([query])[0]
        query_tokens = set(normalize_text(query).split())
        matches: list[tuple[Decimal, RetrievedCandidateEvidence]] = []
        for record in self._records:
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
                    else "The deterministic embedding ranked this verified evidence as related."
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


class CandidateEvidenceRetriever:
    """Build and query stable verified evidence chunks for one candidate profile."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self.provider = provider or build_embedding_provider()

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
        store = LocalVectorStore(self.provider)
        store.index(self.collect(candidate))
        return store.search(query, top_k=top_k, categories=categories)


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
