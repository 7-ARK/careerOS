"""Curated retrieval evaluation for the three CareerOS ranking modes.

From ``backend/``::

    python -m scripts.retrieval_eval

The command scores a frozen 24-case benchmark with the existing ranker.
Lexical-only reorders that ranker's lexical scores. Feature-hash hybrid calls
``rank_evidence`` with ``DeterministicHashEmbeddingProvider``. OpenAI semantic
hybrid calls the same ranker with ``OpenAIEmbeddingProvider`` when
``OPENAI_API_KEY`` is set, and reuses vectors by content hash. A missing key
leaves the semantic arm unmeasured.

Product ranking weights, chunking, and match rules are unchanged. The command
never prints an API key.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from dotenv import load_dotenv

from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.pgvector_store import evidence_content_hash
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
    OpenAIEmbeddingProvider,
    RetrievedCandidateEvidence,
    rank_evidence,
)
from app.models import (
    CandidateProfile,
    Certification,
    Education,
    Project,
    Skill,
    WorkExperience,
)
from app.models.enums import RequirementMatchStatus
from app.schemas import CandidateEvidence, JobRequirement
from scripts.seed_candidate import SKILLS, _projects
from scripts.semantic_embedding_smoke import estimate_embedding_cost_usd, redact_sensitive

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = BACKEND_ROOT / "evals" / "fixtures" / "retrieval" / "retrieval_benchmark.json"
DEFAULT_RESULTS_PATH = BACKEND_ROOT / "evals" / "results" / "results.json"
DEFAULT_REPORT_PATH = BACKEND_ROOT / "evals" / "results" / "retrieval_report.md"
CACHE_DIRECTORY = BACKEND_ROOT / "evals" / "cache"

EVAL_NAMESPACE = uuid5(NAMESPACE_URL, "careeros-retrieval-eval-amina-rahman")
STATUS_TOP_K = 3
RECALL_CUTOFFS = (1, 3)
VECTOR_CITATION_FLOOR = Decimal("0.45")
MISSING_RANK = 10**6
CATEGORIES = ("exact", "paraphrase", "near_miss", "unsupported")
STATUS_LABELS = tuple(status.value for status in RequirementMatchStatus)
POSITIVE_STATUSES = {
    RequirementMatchStatus.MATCHED.value,
    RequirementMatchStatus.PARTIALLY_MATCHED.value,
}
CATEGORY_LABELS = {
    "exact": "exact",
    "paraphrase": "paraphrase",
    "near_miss": "near-miss",
    "unsupported": "unsupported",
}
MODES = ("lexical", "feature_hash_hybrid", "openai_semantic_hybrid")
MODE_LABELS = {
    "lexical": "Lexical only",
    "feature_hash_hybrid": "Feature-hash hybrid",
    "openai_semantic_hybrid": "OpenAI semantic hybrid",
}
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"

PROFILE_SUMMARY = (
    "Early-career backend developer focused on Python, FastAPI, AI-assisted "
    "workflow automation, structured-data extraction, and practical browser "
    "automation. Builds maintainable API services and evidence-backed automation "
    "tools for document and job workflows."
)
EDUCATION_DESCRIPTION = (
    "Studied software engineering, databases, web development, and applied "
    "machine-learning fundamentals."
)
NORTHSTAR_DESCRIPTION = (
    "Builds Python backend services and workflow automations for internal "
    "operations, document processing, and data collection."
)
NORTHSTAR_ACHIEVEMENTS = [
    "Built FastAPI endpoints and PostgreSQL-backed services for structured records.",
    "Automated repetitive workflows with APIs, webhooks, n8n, and Zapier.",
    "Integrated Playwright browser automation for authorized data-collection tasks.",
    "Added Docker-based local environments and GitHub pull-request workflows.",
]
CIVIC_DESCRIPTION = (
    "Supported a small engineering team building Python utilities for document "
    "processing and structured-data extraction."
)
CIVIC_ACHIEVEMENTS = [
    "Extracted structured data from unstructured text and OCR output.",
    "Created SQL queries and validation checks for document-processing records.",
    "Wrote maintainable automation scripts and documented repeatable workflows.",
]


class _Embedder(Protocol):
    provider_name: str
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    """One collected evidence chunk and its stable benchmark key."""

    key: str
    evidence: CandidateEvidence


@dataclass(frozen=True, slots=True)
class Corpus:
    """In-memory demo profile and the chunks ``collect`` actually emits."""

    candidate: CandidateProfile
    records: tuple[CorpusRecord, ...]

    @property
    def by_key(self) -> dict[str, CandidateEvidence]:
        return {record.key: record.evidence for record in self.records}

    @property
    def key_by_id(self) -> dict[str, str]:
        return {record.evidence.evidence_id: record.key for record in self.records}


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One frozen query and its human ground truth."""

    id: str
    category: str
    query: str
    relevant: tuple[str, ...]
    distractors: tuple[str, ...]
    expected_status: str
    ground_truth: str


def stable_id(name: str) -> UUID:
    """Return a UUID that stays put across eval runs."""
    return uuid5(EVAL_NAMESPACE, name)


def build_demo_candidate() -> CandidateProfile:
    """Rebuild the Amina Rahman demo profile without a database.

    Narrative fields are the same strings ``scripts.seed_candidate`` stores.
    Projects and skills come from that module so the eval cannot invent a
    different work history.
    """
    candidate = CandidateProfile(
        id=stable_id("profile"),
        user_id=stable_id("user"),
        full_name="Amina Rahman",
        email="amina.rahman.dev@example.com",
        headline="AI Automation and Backend Developer",
        summary=PROFILE_SUMMARY,
        location="Remote",
    )
    candidate.education = [
        Education(
            id=stable_id("education:Metro Institute of Technology"),
            institution="Metro Institute of Technology",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
            start_date=date(2020, 9, 1),
            end_date=date(2024, 6, 30),
            description=EDUCATION_DESCRIPTION,
        )
    ]
    candidate.work_experiences = [
        WorkExperience(
            id=stable_id("experience:Northstar Digital Studio"),
            company="Northstar Digital Studio",
            job_title="Junior Backend and Automation Developer",
            employment_type="Full-time",
            location="Remote",
            start_date=date(2024, 7, 1),
            is_current=True,
            description=NORTHSTAR_DESCRIPTION,
            achievements=list(NORTHSTAR_ACHIEVEMENTS),
        ),
        WorkExperience(
            id=stable_id("experience:Civic Tech Lab"),
            company="Civic Tech Lab",
            job_title="Software Automation Intern",
            employment_type="Internship",
            location="Hybrid",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            is_current=False,
            description=CIVIC_DESCRIPTION,
            achievements=list(CIVIC_ACHIEVEMENTS),
        ),
    ]
    candidate.projects = [
        Project(
            id=stable_id(f"project:{project.title}"),
            title=project.title,
            description=project.description,
            technologies=list(project.technologies),
            outcomes=list(project.outcomes),
            github_url=project.github_url,
        )
        for project in _projects()
    ]
    candidate.skills = [
        Skill(
            id=stable_id(f"skill:{name}"),
            name=name,
            category=category,
            self_rating=rating,
            years_of_experience=Decimal(years),
        )
        for name, category, rating, years in SKILLS
    ]
    candidate.certifications = [
        Certification(
            id=stable_id("certification:Postman"),
            name="Postman API Fundamentals Student Expert",
            issuing_organization="Postman",
            issue_date=date(2024, 8, 1),
        )
    ]
    return candidate


def _record_key(evidence: CandidateEvidence) -> str:
    label = str(evidence.metadata.get("label", ""))
    if evidence.category == "profile":
        return "profile"
    if evidence.category == "skill":
        return f"skill:{label}"
    if evidence.category == "project":
        return f"project:{label}"
    if evidence.category == "experience":
        if "Northstar Digital Studio" in label:
            return "experience:Northstar Digital Studio"
        if "Civic Tech Lab" in label:
            return "experience:Civic Tech Lab"
    if evidence.category == "education":
        return "education:Metro Institute of Technology"
    if evidence.category == "certification":
        return "certification:Postman"
    raise ValueError(f"unmapped evidence chunk {evidence.evidence_id}")


def build_corpus() -> Corpus:
    """Collect evidence through the product retriever."""
    candidate = build_demo_candidate()
    retriever = CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider())
    evidence = retriever.collect(candidate)
    records = tuple(CorpusRecord(key=_record_key(item), evidence=item) for item in evidence)
    keys = [record.key for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("evidence keys must be unique")
    return Corpus(candidate=candidate, records=records)


def load_benchmark(path: Path | None = None) -> tuple[BenchmarkCase, ...]:
    """Load and validate the frozen case file."""
    payload = json.loads((path or FIXTURE_PATH).read_text(encoding="utf-8"))
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("retrieval benchmark must contain cases")
    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    seen_queries: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, Mapping):
            raise ValueError("each benchmark case must be an object")
        case = _case_from_mapping(raw)
        if case.id in seen_ids:
            raise ValueError(f"duplicate case id {case.id}")
        if case.query in seen_queries:
            raise ValueError(f"duplicate query for {case.id}")
        seen_ids.add(case.id)
        seen_queries.add(case.query)
        cases.append(case)
    return tuple(cases)


def _case_from_mapping(raw: Mapping[str, object]) -> BenchmarkCase:
    case_id = _required_text(raw, "id")
    category = _required_text(raw, "category")
    query = _required_text(raw, "query")
    expected = _required_text(raw, "expected_status")
    ground_truth = _required_text(raw, "ground_truth")
    relevant = _string_tuple(raw.get("relevant"), field=f"{case_id}.relevant")
    distractors = _string_tuple(raw.get("distractors"), field=f"{case_id}.distractors")
    if category not in CATEGORIES:
        raise ValueError(f"{case_id} has unknown category {category}")
    if expected not in STATUS_LABELS:
        raise ValueError(f"{case_id} has unknown status {expected}")
    if set(relevant) & set(distractors):
        raise ValueError(f"{case_id} lists the same chunk as relevant and distractor")
    if category in {"exact", "paraphrase"} and not relevant:
        raise ValueError(f"{case_id} needs relevant evidence")
    if category in {"near_miss", "unsupported"} and relevant:
        raise ValueError(f"{case_id} is a negative case and cannot name relevant evidence")
    if category in {"near_miss", "unsupported"} and expected != "not_evidenced":
        raise ValueError(f"{case_id} must expect not_evidenced")
    return BenchmarkCase(
        id=case_id,
        category=category,
        query=query,
        relevant=relevant,
        distractors=distractors,
        expected_status=expected,
        ground_truth=ground_truth,
    )


def _required_text(raw: Mapping[str, object], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"benchmark case is missing {field}")
    return value.strip()


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a list of strings")
    items = tuple(item.strip() for item in value)
    if len(items) != len(set(items)):
        raise ValueError(f"{field} contains duplicates")
    return items


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Sequence[str], k: int) -> float | None:
    """Return 1 when any relevant id is inside the first k ranks.

    Cases with no relevant evidence are omitted from recall. An empty relevant
    set is not treated as a hit.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    if not relevant_ids:
        return None
    relevant = set(relevant_ids)
    return 1.0 if any(evidence_id in relevant for evidence_id in ranked_ids[:k]) else 0.0


def first_relevant_rank(ranked_ids: Sequence[str], relevant_ids: Sequence[str]) -> int | None:
    """Return the 1-based rank of the first relevant id, if the case is graded."""
    if not relevant_ids:
        return None
    relevant = set(relevant_ids)
    for index, evidence_id in enumerate(ranked_ids, start=1):
        if evidence_id in relevant:
            return index
    return None


def reciprocal_rank(rank: int | None, *, graded: bool) -> float | None:
    """Return 1/rank for a graded case. A miss is 0. An ungraded case is omitted."""
    if not graded:
        return None
    if rank is None:
        return 0.0
    if rank < 1:
        raise ValueError("rank must be at least 1")
    return 1.0 / rank


def is_unsupported_false_positive(
    category: str,
    expected_status: str,
    predicted_status: str,
) -> bool:
    """Return whether an unsupported case was labeled as supported."""
    return (
        category == "unsupported"
        and expected_status == RequirementMatchStatus.NOT_EVIDENCED.value
        and predicted_status in POSITIVE_STATUSES
    )


def is_near_miss_false_positive(category: str, expected_status: str, predicted_status: str) -> bool:
    """Return whether a near-miss case was labeled as supported."""
    return (
        category == "near_miss"
        and expected_status == RequirementMatchStatus.NOT_EVIDENCED.value
        and predicted_status in POSITIVE_STATUSES
    )


def lexical_sort_key(item: RetrievedCandidateEvidence) -> tuple[Decimal, str]:
    """Order by the product lexical score, then evidence id."""
    return (-item.lexical_score, item.evidence_id)


def neighbor_ranked_first(
    mode: str,
    top: RetrievedCandidateEvidence | None,
    distractor_ids: set[str],
) -> bool:
    """Return whether rank 1 is a labeled neighbor the mode would treat as a candidate.

    Lexical-only counts a neighbor when its lexical score is positive. Hybrid
    modes also count a neighbor at or above the product vector citation floor.
    A zero-score tie broken by evidence id is not a neighbor hit.
    """
    if top is None or top.evidence_id not in distractor_ids:
        return False
    if mode == "lexical":
        return top.lexical_score > 0
    return top.lexical_score > 0 or top.vector_score >= VECTOR_CITATION_FLOOR


class CachingEmbeddingProvider:
    """Reuse vectors by ``(embedding_model, content_hash)`` across eval queries.

    The product pgvector cache uses evidence id plus this same content hash.
    The eval cache sees provider text only, so the hash is the text identity.
    """

    def __init__(self, inner: OpenAIEmbeddingProvider, path: Path) -> None:
        self._inner = inner
        self.provider_name = inner.provider_name
        self.model_name = inner.model_name
        self.path = path
        self.cache_hits = 0
        self.cache_misses = 0
        self._entries: dict[str, list[float]] = {}
        self._load()

    def embed(self, texts: list[str]) -> list[list[float]]:
        missing_texts: list[str] = []
        missing_indexes: list[int] = []
        output: list[list[float] | None] = [None] * len(texts)
        for index, text in enumerate(texts):
            cached = self._entries.get(evidence_content_hash(text))
            if cached is None:
                missing_texts.append(text)
                missing_indexes.append(index)
                continue
            output[index] = list(cached)
            self.cache_hits += 1
        if missing_texts:
            vectors = self._inner.embed(missing_texts)
            if len(vectors) != len(missing_texts):
                raise ValueError("embedding provider returned an unexpected vector count")
            for index, text, vector in zip(missing_indexes, missing_texts, vectors, strict=True):
                cleaned = [float(value) for value in vector]
                self._entries[evidence_content_hash(text)] = cleaned
                output[index] = cleaned
                self.cache_misses += 1
            self.save()
        return [list(vector or []) for vector in output]

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("embedding_model") != self.model_name:
            return
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return
        for key, vector in entries.items():
            if isinstance(key, str) and isinstance(vector, list):
                self._entries[key] = [float(value) for value in vector]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "embedding_model": self.model_name,
            "entries": self._entries,
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")


class PrefetchedRetriever(CandidateEvidenceRetriever):
    """Serve one already ranked list to the product status function."""

    def __init__(
        self,
        provider: _Embedder,
        ranked: Sequence[RetrievedCandidateEvidence],
    ) -> None:
        super().__init__(provider)  # type: ignore[arg-type]
        self._ranked = list(ranked)

    def retrieve(
        self,
        candidate: CandidateProfile,
        query: str,
        *,
        top_k: int = 3,
        categories: set[str] | None = None,
    ) -> list[RetrievedCandidateEvidence]:
        if categories:
            raise ValueError("the retrieval eval does not filter status retrieval by category")
        del candidate, query
        return self._ranked[:top_k]


def rank_corpus(
    provider: _Embedder,
    corpus: Corpus,
    query: str,
) -> list[RetrievedCandidateEvidence]:
    """Rank the frozen corpus with the product hybrid function."""
    retriever = CandidateEvidenceRetriever(provider)  # type: ignore[arg-type]
    evidence = [record.evidence for record in corpus.records]
    vectors = retriever.vector_index.sync(corpus.candidate.id, evidence)
    if not vectors:
        return []
    return rank_evidence(provider, vectors, query, top_k=len(vectors))  # type: ignore[arg-type]


def status_for_ranking(
    provider: _Embedder,
    corpus: Corpus,
    query: str,
    ranked: Sequence[RetrievedCandidateEvidence],
    *,
    case_id: str,
) -> str:
    """Apply ``EvidenceMatchService`` to a mode's top-k list."""
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = PrefetchedRetriever(provider, ranked)
    requirement = JobRequirement(
        requirement_id=f"req-{case_id}"[:100],
        text=query,
        kind="technology",
        priority="required",
    )
    match = service._match_requirement(corpus.candidate, requirement, top_k=STATUS_TOP_K)
    return match.status.value


def _zero_vector_for_lexical(
    ranked: Sequence[RetrievedCandidateEvidence],
) -> list[RetrievedCandidateEvidence]:
    """Drop vector admission before the lexical-only status call."""
    return [
        item.model_copy(
            update={
                "vector_score": Decimal("0.0000"),
                "retrieval_score": item.lexical_score,
            }
        )
        for item in ranked
    ]


def evaluate_case(
    mode: str,
    provider: _Embedder,
    corpus: Corpus,
    case: BenchmarkCase,
    ranked: Sequence[RetrievedCandidateEvidence],
) -> dict[str, object]:
    """Score one case from a full ranking."""
    key_by_id = corpus.key_by_id
    ordered = list(ranked)
    status_ranked: Sequence[RetrievedCandidateEvidence] = ordered
    if mode == "lexical":
        ordered = sorted(ordered, key=lexical_sort_key)
        status_ranked = _zero_vector_for_lexical(ordered)
    ranked_ids = [item.evidence_id for item in ordered]
    relevant_ids = [corpus.by_key[key].evidence_id for key in case.relevant]
    distractor_ids = {corpus.by_key[key].evidence_id for key in case.distractors}
    rank = first_relevant_rank(ranked_ids, relevant_ids)
    graded = bool(case.relevant)
    predicted = status_for_ranking(
        provider,
        corpus,
        case.query,
        status_ranked,
        case_id=case.id,
    )
    recalls = {
        f"recall_at_{k}": recall_at_k(ranked_ids, relevant_ids, k) for k in RECALL_CUTOFFS
    }
    top = ordered[0] if ordered else None
    return {
        "id": case.id,
        "category": case.category,
        "query": case.query,
        "expected_status": case.expected_status,
        "predicted_status": predicted,
        "status_correct": predicted == case.expected_status,
        "relevant_keys": list(case.relevant),
        "graded_for_recall": graded,
        "first_relevant_rank": rank,
        "relevant_found": (rank is not None) if graded else None,
        "reciprocal_rank": reciprocal_rank(rank, graded=graded),
        **recalls,
        "unsupported_false_positive": is_unsupported_false_positive(
            case.category,
            case.expected_status,
            predicted,
        ),
        "near_miss_false_positive": is_near_miss_false_positive(
            case.category,
            case.expected_status,
            predicted,
        ),
        "neighbor_ranked_first": neighbor_ranked_first(mode, top, distractor_ids),
        "top_hits": [
            _hit_payload(item, key_by_id, rank=index)
            for index, item in enumerate(ordered[:5], start=1)
        ],
    }


def _hit_payload(
    item: RetrievedCandidateEvidence,
    key_by_id: Mapping[str, str],
    *,
    rank: int,
) -> dict[str, object]:
    return {
        "rank": rank,
        "key": key_by_id.get(item.evidence_id, item.evidence_id),
        "evidence_id": item.evidence_id,
        "lexical_score": f"{item.lexical_score:.4f}",
        "vector_score": f"{item.vector_score:.4f}",
        "retrieval_score": f"{item.retrieval_score:.4f}",
    }


def summarize_mode(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Aggregate recall, MRR, status accuracy, and false positives."""
    return {
        "overall": _summarize_slice(cases),
        "by_category": {
            category: _summarize_slice([case for case in cases if case["category"] == category])
            for category in CATEGORIES
        },
    }


def _summarize_slice(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    graded = [case for case in cases if case["graded_for_recall"]]
    recall_1_hits = sum(int(case["recall_at_1"] == 1.0) for case in graded)
    recall_3_hits = sum(int(case["recall_at_3"] == 1.0) for case in graded)
    reciprocal_values = [float(case["reciprocal_rank"]) for case in graded]
    status_correct = sum(int(bool(case["status_correct"])) for case in cases)
    unsupported_ids = [
        str(case["id"]) for case in cases if case["unsupported_false_positive"]
    ]
    near_miss_ids = [str(case["id"]) for case in cases if case["near_miss_false_positive"]]
    neighbor_ids = [str(case["id"]) for case in cases if case["neighbor_ranked_first"]]
    unsupported_cases = sum(int(case["category"] == "unsupported") for case in cases)
    near_miss_cases = sum(int(case["category"] == "near_miss") for case in cases)
    neighbor_pool = sum(int(bool(case.get("has_distractors", False))) for case in cases)
    return {
        "cases": len(cases),
        "recall_at_1": _ratio(recall_1_hits, len(graded)),
        "recall_at_3": _ratio(recall_3_hits, len(graded)),
        "mrr": {
            "mean": _mean(reciprocal_values),
            "graded_cases": len(graded),
        },
        "status_accuracy": _ratio(status_correct, len(cases)),
        "unsupported_false_positives": {
            "count": len(unsupported_ids),
            "cases": unsupported_cases,
            "case_ids": unsupported_ids,
        },
        "near_miss_false_positives": {
            "count": len(near_miss_ids),
            "cases": near_miss_cases,
            "case_ids": near_miss_ids,
        },
        "neighbor_ranked_first": {
            "count": len(neighbor_ids),
            "cases": neighbor_pool,
            "case_ids": neighbor_ids,
        },
    }


def _ratio(hits: int, total: int) -> dict[str, object]:
    return {
        "hits": hits,
        "cases": total,
        "mean": None if total == 0 else round(hits / total, 6),
    }


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def compare_modes(
    baseline: Sequence[Mapping[str, object]],
    other: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """List cases whose rank, status, or neighbor flag changed."""
    by_id = {str(case["id"]): case for case in other}
    changes: list[dict[str, object]] = []
    for base in baseline:
        case_id = str(base["id"])
        candidate = by_id[case_id]
        retrieval = _rank_change(base, candidate)
        status = _status_change(base, candidate)
        neighbor = _neighbor_change(base, candidate)
        if retrieval == status == neighbor == "unchanged":
            continue
        changes.append(
            {
                "id": case_id,
                "category": base["category"],
                "retrieval": retrieval,
                "status": status,
                "neighbor": neighbor,
                "detail": _change_detail(base, candidate),
            }
        )
    helped = [item["id"] for item in changes if _moved(item, "helped")]
    hurt = [item["id"] for item in changes if _moved(item, "hurt")]
    return {"helped_case_ids": helped, "hurt_case_ids": hurt, "changes": changes}


def _moved(change: Mapping[str, object], direction: str) -> bool:
    return direction in {change["retrieval"], change["status"], change["neighbor"]}


def _rank_change(base: Mapping[str, object], other: Mapping[str, object]) -> str:
    if not base["graded_for_recall"]:
        return "unchanged"
    base_rank = _comparable_rank(base)
    other_rank = _comparable_rank(other)
    if other_rank < base_rank:
        return "helped"
    if other_rank > base_rank:
        return "hurt"
    return "unchanged"


def _comparable_rank(case: Mapping[str, object]) -> int:
    rank = case["first_relevant_rank"]
    if isinstance(rank, int):
        return rank
    return MISSING_RANK


def _status_change(base: Mapping[str, object], other: Mapping[str, object]) -> str:
    base_ok = bool(base["status_correct"])
    other_ok = bool(other["status_correct"])
    if other_ok and not base_ok:
        return "helped"
    if base_ok and not other_ok:
        return "hurt"
    return "unchanged"


def _neighbor_change(base: Mapping[str, object], other: Mapping[str, object]) -> str:
    base_hit = bool(base["neighbor_ranked_first"])
    other_hit = bool(other["neighbor_ranked_first"])
    if base_hit and not other_hit:
        return "helped"
    if other_hit and not base_hit:
        return "hurt"
    return "unchanged"


def _change_detail(base: Mapping[str, object], other: Mapping[str, object]) -> str:
    return (
        f"relevant rank {_rank_text(base)} -> {_rank_text(other)}; "
        f"status {base['predicted_status']} -> {other['predicted_status']}; "
        f"neighbor_ranked_first {base['neighbor_ranked_first']} -> {other['neighbor_ranked_first']}"
    )


def _rank_text(case: Mapping[str, object]) -> str:
    if not case["graded_for_recall"]:
        return "n/a"
    rank = case["first_relevant_rank"]
    return "miss" if rank is None else str(rank)


def _attach_distractor_flag(
    cases: Sequence[BenchmarkCase],
    rows: list[dict[str, object]],
) -> None:
    flagged = {case.id for case in cases if case.distractors}
    for row in rows:
        row["has_distractors"] = row["id"] in flagged


def run_ranked_mode(
    mode: str,
    provider: _Embedder,
    corpus: Corpus,
    cases: Sequence[BenchmarkCase],
) -> dict[str, object]:
    """Embed the corpus once per query and score every case."""
    rows: list[dict[str, object]] = []
    for case in cases:
        ranked = rank_corpus(provider, corpus, case.query)
        rows.append(evaluate_case(mode, provider, corpus, case, ranked))
    _attach_distractor_flag(cases, rows)
    return {
        "ran": True,
        "provider_name": provider.provider_name,
        "model_name": provider.model_name,
        "metrics": summarize_mode(rows),
        "cases": rows,
    }


def _resolve_keys(corpus: Corpus, cases: Sequence[BenchmarkCase]) -> None:
    known = set(corpus.by_key)
    for case in cases:
        missing = [key for key in (*case.relevant, *case.distractors) if key not in known]
        if missing:
            raise KeyError(f"{case.id} references unknown evidence keys: {', '.join(missing)}")


def evaluate_benchmark(
    *,
    include_openai: bool,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
    timeout_seconds: int = 30,
    cache_path: Path | None = None,
    fixture_path: Path | None = None,
) -> dict[str, object]:
    """Score lexical and feature-hash modes, and OpenAI when a key is supplied."""
    cases = load_benchmark(fixture_path)
    corpus = build_corpus()
    _resolve_keys(corpus, cases)
    lexical_provider = DeterministicHashEmbeddingProvider()
    feature_hash = run_ranked_mode("lexical", lexical_provider, corpus, cases)
    # Lexical ranking still calls the product scorer, then reorders by lexical score.
    feature_hash["mode"] = "lexical"
    feature_hash["ranking"] = "lexical_score desc, evidence_id asc"
    feature_hash["status_vector_policy"] = "vector_score forced to 0 before status"
    hybrid = run_ranked_mode("feature_hash_hybrid", lexical_provider, corpus, cases)
    hybrid["mode"] = "feature_hash_hybrid"
    hybrid["ranking"] = "rank_evidence order (lexical 0.7 / vector 0.3)"
    semantic = _semantic_mode(
        include_openai=include_openai,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        timeout_seconds=timeout_seconds,
        cache_path=cache_path,
        corpus=corpus,
        cases=cases,
    )
    payload: dict[str, object] = {
        "benchmark": _benchmark_header(cases, corpus),
        "modes": {
            "lexical": feature_hash,
            "feature_hash_hybrid": hybrid,
            "openai_semantic_hybrid": semantic,
        },
        "comparisons": {
            "feature_hash_hybrid_vs_lexical": compare_modes(
                feature_hash["cases"],  # type: ignore[arg-type]
                hybrid["cases"],  # type: ignore[arg-type]
            )
        },
    }
    if semantic["ran"]:
        payload["comparisons"] = {
            **payload["comparisons"],  # type: ignore[arg-type]
            "openai_semantic_hybrid_vs_lexical": compare_modes(
                feature_hash["cases"],  # type: ignore[arg-type]
                semantic["cases"],  # type: ignore[arg-type]
            ),
            "openai_semantic_hybrid_vs_feature_hash_hybrid": compare_modes(
                hybrid["cases"],  # type: ignore[arg-type]
                semantic["cases"],  # type: ignore[arg-type]
            ),
        }
    payload["recommendation"] = recommendation_for(payload)
    return payload


def _benchmark_header(cases: Sequence[BenchmarkCase], corpus: Corpus) -> dict[str, object]:
    counts = {category: sum(case.category == category for case in cases) for category in CATEGORIES}
    return {
        "name": "CareerOS curated retrieval benchmark",
        "version": 1,
        "fixture": "evals/fixtures/retrieval/retrieval_benchmark.json",
        "corpus": "amina_rahman_demo_seed",
        "corpus_source": (
            "scripts.seed_candidate Amina Rahman demo profile, "
            "collected by CandidateEvidenceRetriever.collect"
        ),
        "case_count": len(cases),
        "category_counts": counts,
        "corpus_chunks": [
            {
                "key": record.key,
                "evidence_id": record.evidence.evidence_id,
                "category": record.evidence.category,
                "content_hash": evidence_content_hash(record.evidence.text),
                "text": record.evidence.text,
            }
            for record in corpus.records
        ],
        "status_labels": list(STATUS_LABELS),
        "status_top_k": STATUS_TOP_K,
        "hybrid_ranking": "rank_evidence lexical 0.7 / vector 0.3; no reranker; no ANN",
        "recall_scope": (
            "Recall@k and MRR average only cases with relevant evidence "
            "(exact and paraphrase). Near-miss and unsupported cases have no relevant "
            "chunk, so those metrics are omitted there."
        ),
        "false_positive_definition": (
            "An unsupported false positive is an unsupported case whose predicted "
            "status is matched or partially_matched. Near-miss false positives use the "
            "same status rule. neighbor_ranked_first means rank 1 is a labeled distractor "
            "with lexical_score > 0, or, for hybrid modes, vector_score >= 0.45."
        ),
    }


def _semantic_mode(
    *,
    include_openai: bool,
    openai_api_key: str | None,
    openai_model: str | None,
    timeout_seconds: int,
    cache_path: Path | None,
    corpus: Corpus,
    cases: Sequence[BenchmarkCase],
) -> dict[str, object]:
    model_name = (openai_model or DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    key = (openai_api_key or "").strip()
    if not include_openai or not key:
        return {
            "ran": False,
            "provider_name": "openai",
            "model_name": model_name,
            "reason": (
                "OPENAI_API_KEY is not set, so the semantic arm was not run. "
                "No OpenAI score was invented. Re-run `python -m scripts.retrieval_eval` "
                "from backend/ with OPENAI_API_KEY set. The default model is "
                f"{DEFAULT_OPENAI_MODEL}. RAG_EMBEDDING_MODEL overrides it. "
                "Leave RAG_EMBEDDING_DIMENSIONS unset unless you intend to request "
                "a shortened vector."
            ),
            "metrics": None,
            "cases": None,
            "usage": None,
        }
    provider = OpenAIEmbeddingProvider(
        api_key=key,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        dimensions=None,
    )
    cache_file = cache_path or (CACHE_DIRECTORY / f"openai-{_slug(model_name)}.json")
    cached = CachingEmbeddingProvider(provider, cache_file)
    try:
        result = run_ranked_mode("openai_semantic_hybrid", cached, corpus, cases)
    except Exception as exc:
        return {
            "ran": False,
            "provider_name": "openai",
            "model_name": model_name,
            "reason": (
                "The OpenAI arm failed before scores were recorded. "
                + public_error(exc, key)
            ),
            "metrics": None,
            "cases": None,
            "usage": _usage_payload(provider, cached),
        }
    result["mode"] = "openai_semantic_hybrid"
    result["ranking"] = "rank_evidence order (lexical 0.7 / vector 0.3)"
    result["usage"] = _usage_payload(provider, cached)
    result["cache_path"] = str(cache_file.relative_to(BACKEND_ROOT))
    return result


def public_error(exc: BaseException, secret: str) -> str:
    """Render an exception without embedding the API key."""
    text = f"{type(exc).__name__}: {exc}"
    return redact_sensitive(text, (secret,))


def _usage_payload(
    provider: OpenAIEmbeddingProvider,
    cached: CachingEmbeddingProvider,
) -> dict[str, object]:
    tokens = provider.usage.prompt_tokens
    cost = estimate_embedding_cost_usd(provider.model_name, tokens)
    return {
        "embedding_model": provider.model_name,
        "api_requests": provider.usage.requests,
        "prompt_tokens": tokens,
        "cache_hits": cached.cache_hits,
        "cache_misses": cached.cache_misses,
        "estimated_cost_usd": None if cost is None else f"{cost:.8f}",
        "cost_note": (
            "Approximate list-price estimate from the published per-million-token "
            "table used by scripts.semantic_embedding_smoke. It is not an invoice."
        ),
    }


def _slug(model_name: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-" for char in model_name
    )
    return cleaned or "model"


def recommendation_for(payload: Mapping[str, object]) -> dict[str, str]:
    """Recommend one next step from the measured payload. Do not apply it."""
    modes = payload["modes"]
    assert isinstance(modes, Mapping)
    lexical = modes["lexical"]
    feature_hash = modes["feature_hash_hybrid"]
    semantic = modes["openai_semantic_hybrid"]
    assert isinstance(lexical, Mapping)
    assert isinstance(feature_hash, Mapping)
    assert isinstance(semantic, Mapping)
    lexical_metrics = lexical["metrics"]
    feature_metrics = feature_hash["metrics"]
    assert isinstance(lexical_metrics, Mapping)
    assert isinstance(feature_metrics, Mapping)
    lexical_rows = _rows_by_id(lexical)
    feature_rows = _rows_by_id(feature_hash)
    ocr_lexical = lexical_rows["para-ocr"]["first_relevant_rank"]
    ocr_feature = feature_rows["para-ocr"]["first_relevant_rank"]
    ocr_top_lexical = _top_hit(lexical_rows["para-ocr"])["lexical_score"]
    paraphrase_status_hits = [
        case_id
        for case_id, row in feature_rows.items()
        if row["category"] == "paraphrase" and row["status_correct"]
    ]
    framework = feature_rows["para-python-web-framework"]
    framework_top = _top_hit(framework)
    aws = lexical_rows["unsup-aws"]
    aws_top = _top_hit(aws)
    comparisons = payload["comparisons"]
    assert isinstance(comparisons, Mapping)
    versus_lexical = comparisons["feature_hash_hybrid_vs_lexical"]
    assert isinstance(versus_lexical, Mapping)
    helped = _id_list(versus_lexical["helped_case_ids"])
    hurt = _id_list(versus_lexical["hurt_case_ids"])
    status_unchanged = all(
        isinstance(change, Mapping) and change["status"] == "unchanged"
        for change in versus_lexical["changes"]
        if isinstance(versus_lexical["changes"], list)
    )
    if semantic["ran"]:
        semantic_clause = (
            "The OpenAI arm was measured. Quote its paraphrase recall and "
            "false-positive counts from this file before any weight edit."
        )
    else:
        semantic_clause = (
            "The OpenAI arm did not run. This file contains no semantic score. "
            "Re-run with OPENAI_API_KEY on this same fixture before treating "
            "live embeddings as measured."
        )
    if status_unchanged:
        status_sentence = "Status labels on those changed cases stayed the same."
    else:
        status_sentence = "Some of those cases also changed status."
    status_hits = ", ".join(f"`{case_id}`" for case_id in paraphrase_status_hits) or "none"
    parts = [
        "Investigate the lexical status gate. Leave the 0.7 / 0.3 weights in place.",
        "Exact Recall@1 is "
        f"{_category_recall(lexical_metrics, 'exact', 'recall_at_1')} lexical and "
        f"{_category_recall(feature_metrics, 'exact', 'recall_at_1')} feature-hash, "
        "with status "
        f"{_category_status(lexical_metrics, 'exact')} and "
        f"{_category_status(feature_metrics, 'exact')}.",
        "Unsupported false positives are "
        f"{_false_positive_count(lexical_metrics, 'unsupported_false_positives')} "
        "lexical and "
        f"{_false_positive_count(feature_metrics, 'unsupported_false_positives')} "
        "feature-hash.",
        "Near-miss false positives are "
        f"{_false_positive_count(lexical_metrics, 'near_miss_false_positives')} "
        "lexical and "
        f"{_false_positive_count(feature_metrics, 'near_miss_false_positives')} "
        "feature-hash.",
        "On the lexical arm, `unsup-aws` tops out at lexical "
        f"{aws_top['lexical_score']} on "
        f"{aws_top['key']} and stays `{aws['predicted_status']}` under the "
        "explicit AWS phrase rule.",
        "Paraphrase Recall@1 is "
        f"{_category_recall(lexical_metrics, 'paraphrase', 'recall_at_1')} lexical and "
        f"{_category_recall(feature_metrics, 'paraphrase', 'recall_at_1')} feature-hash.",
        "Paraphrase Recall@3 is "
        f"{_category_recall(lexical_metrics, 'paraphrase', 'recall_at_3')} lexical and "
        f"{_category_recall(feature_metrics, 'paraphrase', 'recall_at_3')} feature-hash.",
        f"`para-ocr` is outside the top 3 at rank {ocr_lexical} lexical and rank "
        f"{ocr_feature} feature-hash, with status `not_evidenced` and a top-hit "
        f"lexical score of {ocr_top_lexical}.",
        "Paraphrase status accuracy is "
        f"{_category_status(lexical_metrics, 'paraphrase')} lexical and "
        f"{_category_status(feature_metrics, 'paraphrase')} feature-hash.",
        f"Paraphrase cases with a correct feature-hash status: {status_hits}. "
        f"`para-python-web-framework` has feature-hash top hit {framework_top['key']} "
        f"at lexical {framework_top['lexical_score']}, a labeled distractor.",
        f"Feature-hash versus lexical helped: {helped}. Hurt: {hurt}.",
        status_sentence,
        "Overall Recall@1 is "
        f"{_overall_recall(lexical_metrics, 'recall_at_1')} lexical and "
        f"{_overall_recall(feature_metrics, 'recall_at_1')} feature-hash.",
        semantic_clause,
        "The measured rank movement is too small to justify a weight change, "
        "and a zero-lexical chunk stays below the product's 0.65 lexical bar "
        "for `matched`.",
    ]
    text = " ".join(parts)
    return {"choice": "investigate", "text": text}


def _rows_by_id(mode_payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    cases = mode_payload["cases"]
    assert isinstance(cases, list)
    rows: dict[str, Mapping[str, object]] = {}
    for case in cases:
        assert isinstance(case, Mapping)
        rows[str(case["id"])] = case
    return rows


def _top_hit(case: Mapping[str, object]) -> Mapping[str, object]:
    hits = case["top_hits"]
    assert isinstance(hits, list) and hits
    top = hits[0]
    assert isinstance(top, Mapping)
    return top


def _false_positive_count(metrics: Mapping[str, object], field: str) -> str:
    overall = metrics["overall"]
    assert isinstance(overall, Mapping)
    bucket = overall[field]
    assert isinstance(bucket, Mapping)
    return f"{bucket['count']}/{bucket['cases']}"


def _overall_recall(metrics: Mapping[str, object], field: str) -> str:
    overall = metrics["overall"]
    assert isinstance(overall, Mapping)
    ratio = overall[field]
    assert isinstance(ratio, Mapping)
    return f"{ratio['hits']}/{ratio['cases']}"


def _category_recall(metrics: Mapping[str, object], category: str, field: str) -> str:
    by_category = metrics["by_category"]
    assert isinstance(by_category, Mapping)
    slice_metrics = by_category[category]
    assert isinstance(slice_metrics, Mapping)
    ratio = slice_metrics[field]
    assert isinstance(ratio, Mapping)
    hits = ratio["hits"]
    cases = ratio["cases"]
    return f"{hits}/{cases}"


def _category_status(metrics: Mapping[str, object], category: str) -> str:
    by_category = metrics["by_category"]
    assert isinstance(by_category, Mapping)
    slice_metrics = by_category[category]
    assert isinstance(slice_metrics, Mapping)
    ratio = slice_metrics["status_accuracy"]
    assert isinstance(ratio, Mapping)
    return f"{ratio['hits']}/{ratio['cases']}"


def render_report(payload: Mapping[str, object]) -> str:
    """Render the human-readable report from the machine-readable payload."""
    benchmark = payload["benchmark"]
    modes = payload["modes"]
    comparisons = payload["comparisons"]
    recommendation = payload["recommendation"]
    assert isinstance(benchmark, Mapping)
    assert isinstance(modes, Mapping)
    assert isinstance(comparisons, Mapping)
    assert isinstance(recommendation, Mapping)
    counts = benchmark["category_counts"]
    assert isinstance(counts, Mapping)
    lines = [
        "# CareerOS retrieval evaluation",
        "",
        "Evaluation only. This run leaves hybrid weights, chunking, reranking, "
        "and product match rules as they are.",
        "",
        "## Corpus",
        "",
        "The corpus is the Amina Rahman demo profile from `scripts/seed_candidate.py`, "
        "turned into chunks by `CandidateEvidenceRetriever.collect`. "
        f"It contains {len(benchmark['corpus_chunks'])} chunks. "
        "Google Cloud, AWS, Kubernetes, and CI/CD are absent from this profile. "
        "Those tools are not treated as demonstrated experience.",
        "",
        "## Benchmark",
        "",
        f"{benchmark['case_count']} frozen cases: "
        f"{counts['exact']} exact, {counts['paraphrase']} paraphrase, "
        f"{counts['near_miss']} near-miss, {counts['unsupported']} unsupported. "
        "Ground truth was written from the chunk text before the three modes were scored.",
        "",
        "| Case | Category | Query | Relevant evidence | Expected status |",
        "| --- | --- | --- | --- | --- |",
    ]
    lexical_cases = modes["lexical"]
    assert isinstance(lexical_cases, Mapping)
    # Case metadata lives on every mode; lexical always runs.
    for case in lexical_cases["cases"]:  # type: ignore[index]
        assert isinstance(case, Mapping)
        relevant = ", ".join(case["relevant_keys"]) or "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case["id"]),
                    CATEGORY_LABELS[str(case["category"])],
                    _cell(case["query"]),
                    _cell(relevant),
                    _cell(case["expected_status"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Metric definitions",
            "",
            "- **Recall@k** is 1 when at least one relevant chunk is in the first k "
            "ranks of the full corpus ranking. The reported value is that count "
            "over the cases that have relevant evidence.",
            "- **MRR** is the mean of 1/rank for those same graded cases. "
            "A graded miss contributes 0.",
            "- Near-miss and unsupported cases have no relevant chunk. Recall and MRR "
            "are omitted for them.",
            "- **Status** uses `EvidenceMatchService._match_requirement` on the mode's "
            "top 3. Labels are `matched`, `partially_matched`, `not_evidenced`, and "
            "`not_applicable`. Requirement kind is `technology`, so the experience-year "
            "path stays unused.",
            "- Lexical-only sorts by the lexical score `rank_evidence` already computed, "
            "then sets `vector_score` to 0 before the status call.",
            "- Feature-hash hybrid and OpenAI semantic hybrid keep the `rank_evidence` "
            "order and scores. That function is lexical 0.7 / vector 0.3.",
            "- AWS, Kubernetes, and CI/CD queries hit the product's explicit phrase rules. "
            "Those status labels follow the phrase rule.",
            "- An **unsupported false positive** is an unsupported case predicted "
            "`matched` or `partially_matched`. Near-miss false positives use the same rule.",
            "- **neighbor_ranked_first** means the top chunk is a labeled distractor "
            "with a positive lexical score, or a hybrid vector score of at least 0.45. "
            "An all-zero tie is left uncounted.",
            "",
            "## Results",
            "",
        ]
    )
    for mode in MODES:
        lines.extend(_mode_section(mode, modes[mode]))
    lines.extend(["## Cases helped or hurt", ""])
    lines.extend(
        _comparison_section(
            "Feature-hash hybrid compared with lexical only",
            comparisons.get("feature_hash_hybrid_vs_lexical"),
        )
    )
    if "openai_semantic_hybrid_vs_lexical" in comparisons:
        lines.extend(
            _comparison_section(
                "OpenAI semantic hybrid compared with lexical only",
                comparisons["openai_semantic_hybrid_vs_lexical"],
            )
        )
        lines.extend(
            _comparison_section(
                "OpenAI semantic hybrid compared with feature-hash hybrid",
                comparisons["openai_semantic_hybrid_vs_feature_hash_hybrid"],
            )
        )
    else:
        lines.extend(
            [
                "OpenAI comparisons are omitted because the semantic arm did not run.",
                "",
            ]
        )
    lines.extend(
        [
            "## Recommendation",
            "",
            f"Choice: **{recommendation['choice']}**.",
            "",
            str(recommendation["text"]),
            "",
            "This recommendation is not implemented.",
            "",
            "## How to reproduce",
            "",
            "```text",
            "cd backend",
            "python -m scripts.retrieval_eval",
            "```",
            "",
            "The command writes `evals/results/results.json` and "
            "`evals/results/retrieval_report.md`. "
            "With `OPENAI_API_KEY` set, it also runs the semantic arm and caches "
            "vectors under `evals/cache/`. "
            "That cache is local reuse and is gitignored. `RAG_EMBEDDING_MODEL` defaults to "
            f"`{DEFAULT_OPENAI_MODEL}`. The command does not print the key.",
            "",
        ]
    )
    return "\n".join(lines)


def _mode_section(mode: str, payload: object) -> list[str]:
    assert isinstance(payload, Mapping)
    lines = [f"### {MODE_LABELS[mode]}", ""]
    if not payload["ran"]:
        lines.extend([str(payload["reason"]), ""])
        return lines
    lines.append(
        f"Provider `{payload['provider_name']}`, model `{payload['model_name']}`."
    )
    lines.append(f"Ranking: {payload['ranking']}.")
    lines.append("")
    metrics = payload["metrics"]
    assert isinstance(metrics, Mapping)
    lines.extend(_metrics_table(metrics))
    usage = payload.get("usage")
    if isinstance(usage, Mapping):
        lines.extend(
            [
                "",
                (
                    f"OpenAI model `{usage['embedding_model']}` made "
                    f"{usage['api_requests']} embedding request(s) and reported "
                    f"{usage['prompt_tokens']} prompt tokens."
                ),
                (
                    f"Cache hits {usage['cache_hits']}, cache misses {usage['cache_misses']}. "
                    f"Approximate list-price cost: {usage['estimated_cost_usd']} USD."
                ),
                str(usage["cost_note"]),
                "",
            ]
        )
    lines.extend(_case_table(payload["cases"]))
    lines.extend(_false_positive_lines(metrics))
    return lines


def _metrics_table(metrics: Mapping[str, object]) -> list[str]:
    lines = [
        "| Slice | Recall@1 | Recall@3 | MRR | Status accuracy | "
        "Unsupported FP | Near-miss FP | Neighbor at rank 1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    overall = metrics["overall"]
    by_category = metrics["by_category"]
    assert isinstance(overall, Mapping)
    assert isinstance(by_category, Mapping)
    lines.append(_metric_row("Overall", overall))
    for category in CATEGORIES:
        lines.append(_metric_row(CATEGORY_LABELS[category], by_category[category]))
    lines.append("")
    return lines


def _metric_row(label: str, metrics: object) -> str:
    assert isinstance(metrics, Mapping)
    recall_1 = _ratio_text(metrics["recall_at_1"])
    recall_3 = _ratio_text(metrics["recall_at_3"])
    mrr = metrics["mrr"]
    status = _ratio_text(metrics["status_accuracy"])
    unsupported = metrics["unsupported_false_positives"]
    near_miss = metrics["near_miss_false_positives"]
    neighbor = metrics["neighbor_ranked_first"]
    assert isinstance(mrr, Mapping)
    assert isinstance(unsupported, Mapping)
    assert isinstance(near_miss, Mapping)
    assert isinstance(neighbor, Mapping)
    mrr_text = "n/a" if mrr["mean"] is None else f"{mrr['mean']:.4f} (n={mrr['graded_cases']})"
    return (
        f"| {label} | {recall_1} | {recall_3} | {mrr_text} | {status} | "
        f"{_count_text(unsupported)} | {_count_text(near_miss)} | {_count_text(neighbor)} |"
    )


def _count_text(value: Mapping[str, object]) -> str:
    total = value["cases"]
    if not isinstance(total, int) or total == 0:
        return "n/a"
    return f"{value['count']}/{total}"


def _ratio_text(value: object) -> str:
    assert isinstance(value, Mapping)
    if value["cases"] == 0 or value["mean"] is None:
        return "n/a"
    return f"{value['hits']}/{value['cases']}"


def _case_table(cases: object) -> list[str]:
    assert isinstance(cases, list)
    lines = [
        "| Case | Category | Top 1 | Relevant rank | Status | FP | Neighbor |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        assert isinstance(case, Mapping)
        top_hits = case["top_hits"]
        assert isinstance(top_hits, list)
        top_key = top_hits[0]["key"] if top_hits else "—"
        false_positive = bool(
            case["unsupported_false_positive"] or case["near_miss_false_positive"]
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case["id"]),
                    CATEGORY_LABELS[str(case["category"])],
                    _cell(top_key),
                    _rank_text(case),
                    (
                        f"{case['predicted_status']} "
                        f"({'correct' if case['status_correct'] else 'incorrect'})"
                    ),
                    "yes" if false_positive else "no",
                    "yes" if case["neighbor_ranked_first"] else "no",
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _false_positive_lines(metrics: Mapping[str, object]) -> list[str]:
    overall = metrics["overall"]
    assert isinstance(overall, Mapping)
    unsupported = overall["unsupported_false_positives"]
    near_miss = overall["near_miss_false_positives"]
    neighbor = overall["neighbor_ranked_first"]
    assert isinstance(unsupported, Mapping)
    assert isinstance(near_miss, Mapping)
    assert isinstance(neighbor, Mapping)
    return [
        f"Unsupported false positives: {_id_list(unsupported['case_ids'])}.",
        f"Near-miss false positives: {_id_list(near_miss['case_ids'])}.",
        f"Labeled neighbor at rank 1: {_id_list(neighbor['case_ids'])}.",
        "",
    ]


def _id_list(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


def _comparison_section(title: str, comparison: object) -> list[str]:
    assert isinstance(comparison, Mapping)
    lines = [
        f"### {title}",
        "",
        f"Helped: {_id_list(comparison['helped_case_ids'])}.",
        f"Hurt: {_id_list(comparison['hurt_case_ids'])}.",
        "",
    ]
    changes = comparison["changes"]
    if not isinstance(changes, list) or not changes:
        lines.extend(["No rank, status, or neighbor changes.", ""])
        return lines
    lines.extend(
        [
            "| Case | Category | Retrieval | Status | Neighbor | Detail |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for change in changes:
        assert isinstance(change, Mapping)
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(change["id"]),
                    CATEGORY_LABELS[str(change["category"])],
                    str(change["retrieval"]),
                    str(change["status"]),
                    str(change["neighbor"]),
                    _cell(change["detail"]),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def write_artifacts(
    payload: Mapping[str, object],
    *,
    results_path: Path,
    report_path: Path,
) -> None:
    """Write the JSON results and the markdown report."""
    results_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")


def _openai_settings_from_env() -> tuple[str, str, int]:
    load_dotenv(BACKEND_ROOT / ".env")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("RAG_EMBEDDING_MODEL", DEFAULT_OPENAI_MODEL).strip()
    model = model or DEFAULT_OPENAI_MODEL
    raw_timeout = os.environ.get("PROVIDER_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout = int(raw_timeout)
    except ValueError:
        timeout = 30
    if timeout < 1:
        timeout = 30
    return key, model, timeout


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation and write both artifacts."""
    del argv
    key, model, timeout = _openai_settings_from_env()
    payload = evaluate_benchmark(
        include_openai=bool(key),
        openai_api_key=key or None,
        openai_model=model,
        timeout_seconds=timeout,
    )
    write_artifacts(payload, results_path=DEFAULT_RESULTS_PATH, report_path=DEFAULT_REPORT_PATH)
    print(f"wrote {DEFAULT_RESULTS_PATH.relative_to(BACKEND_ROOT)}")
    print(f"wrote {DEFAULT_REPORT_PATH.relative_to(BACKEND_ROOT)}")
    semantic = payload["modes"]["openai_semantic_hybrid"]  # type: ignore[index]
    assert isinstance(semantic, Mapping)
    if semantic["ran"]:
        usage = semantic["usage"]
        assert isinstance(usage, Mapping)
        print(
            "openai "
            f"model={usage['embedding_model']} "
            f"requests={usage['api_requests']} "
            f"prompt_tokens={usage['prompt_tokens']} "
            f"estimated_cost_usd={usage['estimated_cost_usd']}"
        )
    else:
        print("openai semantic arm: not run")
    recommendation = payload["recommendation"]
    assert isinstance(recommendation, Mapping)
    print(f"recommendation={recommendation['choice']}")
    return 0 if semantic["ran"] or not key else 1


if __name__ == "__main__":
    sys.exit(main())
