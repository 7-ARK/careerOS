"""Harness tests for the curated retrieval benchmark. No live OpenAI calls."""

import inspect
from decimal import Decimal
from pathlib import Path

from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.retrieval import VectorRecord, rank_evidence
from app.schemas import CandidateEvidence
from scripts.retrieval_eval import (
    build_corpus,
    evaluate_benchmark,
    first_relevant_rank,
    is_near_miss_false_positive,
    is_unsupported_false_positive,
    load_benchmark,
    public_error,
    recall_at_k,
    reciprocal_rank,
    render_report,
    write_artifacts,
)
from scripts.seed_candidate import SKILLS, _projects

FIXTURE = (
    Path(__file__).parents[2] / "evals" / "fixtures" / "retrieval" / "retrieval_benchmark.json"
)


def test_benchmark_fixture_is_a_frozen_24_case_set() -> None:
    cases = load_benchmark(FIXTURE)
    counts = {category: 0 for category in ("exact", "paraphrase", "near_miss", "unsupported")}
    for case in cases:
        counts[case.category] += 1

    assert len(cases) == 24
    assert counts == {"exact": 8, "paraphrase": 6, "near_miss": 5, "unsupported": 5}
    assert {case.expected_status for case in cases} <= {
        "matched",
        "partially_matched",
        "not_evidenced",
        "not_applicable",
    }
    corpus = build_corpus()
    joined = " ".join(record.evidence.text.casefold() for record in corpus.records)
    for phrase in (
        "amazon web services",
        "kubernetes",
        "terraform",
        "salesforce",
        "swiftui",
        "django",
        "google cloud",
        "continuous integration",
    ):
        assert phrase not in joined
    for case in cases:
        for key in (*case.relevant, *case.distractors):
            assert key in corpus.by_key
        relevant_text = [corpus.by_key[key].text.casefold() for key in case.relevant]
        query = case.query.casefold()
        if case.category == "exact":
            assert any(query in text for text in relevant_text)
        if case.category == "paraphrase":
            assert all(query not in text for text in relevant_text)


def test_corpus_follows_the_demo_seed_and_stable_ids() -> None:
    first = build_corpus()
    second = build_corpus()

    assert [record.key for record in first.records] == [record.key for record in second.records]
    assert [record.evidence.evidence_id for record in first.records] == [
        record.evidence.evidence_id for record in second.records
    ]
    skill_keys = [record.key for record in first.records if record.key.startswith("skill:")]
    project_keys = [record.key for record in first.records if record.key.startswith("project:")]
    assert skill_keys == [f"skill:{name}" for name, *_rest in SKILLS]
    assert project_keys == [f"project:{project.title}" for project in _projects()]
    assert "experience:Northstar Digital Studio" in first.by_key
    assert "experience:Civic Tech Lab" in first.by_key
    assert "Postman API Fundamentals Student Expert" in first.by_key["certification:Postman"].text


def test_metric_helpers_skip_empty_relevant_sets_and_count_false_positives() -> None:
    assert recall_at_k(["b", "a"], ["a"], 1) == 0.0
    assert recall_at_k(["b", "a"], ["a"], 3) == 1.0
    assert recall_at_k(["b"], [], 1) is None
    assert first_relevant_rank(["b", "a", "c"], ["a"]) == 2
    assert first_relevant_rank(["b"], ["a"]) is None
    assert first_relevant_rank(["b"], []) is None
    assert reciprocal_rank(2, graded=True) == 0.5
    assert reciprocal_rank(None, graded=True) == 0.0
    assert reciprocal_rank(1, graded=False) is None
    assert is_unsupported_false_positive("unsupported", "not_evidenced", "matched")
    assert is_unsupported_false_positive("unsupported", "not_evidenced", "partially_matched")
    assert not is_unsupported_false_positive("unsupported", "not_evidenced", "not_evidenced")
    assert not is_unsupported_false_positive("near_miss", "not_evidenced", "matched")
    assert is_near_miss_false_positive("near_miss", "not_evidenced", "partially_matched")
    assert not is_near_miss_false_positive("exact", "matched", "matched")


def test_harness_calls_the_live_hybrid_weight() -> None:
    class _SameVector:
        provider_name = "same"
        model_name = "same-v1"

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _text in texts]

    provider = _SameVector()
    evidence = CandidateEvidence(
        evidence_id="evidence-neighbor",
        source_id=build_corpus().candidate.id,
        category="project",
        text="Deployed applications with Docker.",
    )
    found = rank_evidence(
        provider,  # type: ignore[arg-type]
        [VectorRecord(evidence=evidence, vector=provider.embed([evidence.text])[0])],
        "Kubernetes",
        top_k=1,
    )

    assert found[0].lexical_score == Decimal("0.0000")
    assert found[0].vector_score == Decimal("1.0000")
    assert found[0].retrieval_score == Decimal("0.3000")


def test_citation_floor_matches_the_product_matcher() -> None:
    matcher_source = Path(inspect.getfile(EvidenceMatchService)).read_text(encoding="utf-8")
    ranker_source = Path(inspect.getfile(rank_evidence)).read_text(encoding="utf-8")
    assert 'Decimal("0.45")' in matcher_source
    assert 'Decimal("0.7")' in ranker_source
    assert 'Decimal("0.3")' in ranker_source


def test_offline_benchmark_scores_lexical_and_feature_hash_without_openai(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-eval-key")
    payload = evaluate_benchmark(include_openai=False)
    encoded = __import__("json").dumps(payload)

    assert "super-secret-eval-key" not in encoded
    modes = payload["modes"]
    assert modes["lexical"]["ran"] is True
    assert modes["feature_hash_hybrid"]["ran"] is True
    assert modes["openai_semantic_hybrid"]["ran"] is False
    assert modes["openai_semantic_hybrid"]["metrics"] is None
    assert len(modes["lexical"]["cases"]) == 24
    postman = next(case for case in modes["lexical"]["cases"] if case["id"] == "exact-postman")
    assert postman["first_relevant_rank"] == 1
    assert postman["predicted_status"] == "matched"
    hash_postman = next(
        case for case in modes["feature_hash_hybrid"]["cases"] if case["id"] == "exact-postman"
    )
    assert hash_postman["first_relevant_rank"] == 1

    results_path = tmp_path / "results.json"
    report_path = tmp_path / "retrieval_report.md"
    write_artifacts(payload, results_path=results_path, report_path=report_path)
    report = report_path.read_text(encoding="utf-8")
    assert "exact-postman" in report
    assert "super-secret-eval-key" not in report
    assert render_report(payload) == report


def test_public_error_redacts_the_api_key() -> None:
    message = public_error(
        RuntimeError("rejected key super-secret-eval-key"),
        "super-secret-eval-key",
    )
    assert "super-secret-eval-key" not in message
    assert "[redacted]" in message


class _RecordingProvider:
    provider_name = "recording"
    model_name = "recording-v1"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


def test_embedding_cache_reuses_identical_text(tmp_path: Path) -> None:
    from scripts.retrieval_eval import CachingEmbeddingProvider

    inner = _RecordingProvider()
    cache = CachingEmbeddingProvider(inner, tmp_path / "cache.json")  # type: ignore[arg-type]
    first = cache.embed(["FastAPI", "PostgreSQL"])
    second = cache.embed(["PostgreSQL", "FastAPI"])

    assert first[0] == second[1]
    assert first[1] == second[0]
    assert inner.calls == [["FastAPI", "PostgreSQL"]]
    assert cache.cache_hits == 2
    assert cache.cache_misses == 2

    reloaded = CachingEmbeddingProvider(inner, tmp_path / "cache.json")  # type: ignore[arg-type]
    reloaded.embed(["FastAPI"])
    assert inner.calls == [["FastAPI", "PostgreSQL"]]
