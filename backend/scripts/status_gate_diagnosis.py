"""Offline diagnosis of the product status gate on the frozen retrieval benchmark.

The OpenAI semantic hybrid scores are read from ``evals/results/results.json``.
This module does not call OpenAI, does not retune 0.7/0.3 ranking, and does not
change ``EvidenceMatchService``. Candidate gates are simulated here only.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from app.features.resume_intelligence.matching import (
    EXPLICIT_EVIDENCE_RULES,
    EvidenceMatchService,
)
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
    normalize_text,
)
from app.models.enums import RequirementMatchStatus
from app.schemas import RetrievedCandidateEvidence
from scripts.retrieval_eval import (
    Corpus,
    build_corpus,
    is_near_miss_false_positive,
    is_unsupported_false_positive,
    status_for_ranking,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = BACKEND_ROOT / "evals" / "results" / "results.json"
DEFAULT_DIAGNOSIS_JSON = BACKEND_ROOT / "evals" / "results" / "status_gate_diagnosis.json"
DEFAULT_DIAGNOSIS_MARKDOWN = BACKEND_ROOT / "evals" / "results" / "status_gate_diagnosis.md"

MATCHED_LEXICAL_BAR = Decimal("0.65")
PARTIAL_LEXICAL_BAR = Decimal("0.25")
VECTOR_CITATION_FLOOR = Decimal("0.45")
STATUS_TOP_K = 3
OPTION_VECTOR_MATCH_BAR = Decimal("0.42")
OPTION_PARTIAL_VECTOR_BAR = Decimal("0.30")

MATCHED = RequirementMatchStatus.MATCHED.value
PARTIAL = RequirementMatchStatus.PARTIALLY_MATCHED.value
NOT_EVIDENCED = RequirementMatchStatus.NOT_EVIDENCED.value
NOT_APPLICABLE = RequirementMatchStatus.NOT_APPLICABLE.value

FOCUS_CATEGORIES = ("paraphrase", "near_miss", "unsupported")
OPTION_VECTOR = "vector_top3_0_42"
OPTION_PARTIAL = "same_chunk_lexical_0_25_vector_0_30"


@dataclass(frozen=True, slots=True)
class Hit:
    """One recorded hybrid hit joined back to corpus text."""

    rank: int
    key: str
    lexical_score: Decimal
    vector_score: Decimal
    combined_score: Decimal
    text: str
    overlap_tokens: tuple[str, ...]
    relevant: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "key": self.key,
            "lexical_score": _fmt(self.lexical_score),
            "vector_score": _fmt(self.vector_score),
            "combined_score": _fmt(self.combined_score),
            "overlap_tokens": list(self.overlap_tokens),
            "relevant": self.relevant,
        }


def build_diagnosis(results_path: Path | None = None) -> dict[str, object]:
    """Replay the recorded OpenAI arm and simulate the two candidate gates."""
    path = results_path or DEFAULT_RESULTS_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    mode = _openai_mode(payload)
    corpus = build_corpus()
    provider = DeterministicHashEmbeddingProvider()
    cases = [
        _diagnose_case(raw, corpus=corpus, provider=provider)
        for raw in mode["cases"]
        if isinstance(raw, dict)
    ]
    if len(cases) != 24:
        raise ValueError(f"expected 24 recorded OpenAI cases, found {len(cases)}")
    focus = [case for case in cases if case["category"] in FOCUS_CATEGORIES]
    if len(focus) != 16:
        raise ValueError(f"expected 16 paraphrase/near-miss/unsupported cases, found {len(focus)}")
    options = [_simulate_option(option_id, cases) for option_id in (OPTION_VECTOR, OPTION_PARTIAL)]
    scan = _vector_separability(cases)
    return {
        "source_results": "evals/results/results.json",
        "mode": "openai_semantic_hybrid",
        "provider_name": mode.get("provider_name"),
        "model_name": mode.get("model_name"),
        "ranking": mode.get("ranking"),
        "product_rule": _product_rule_description(),
        "baseline": _metrics(cases, status_key="predicted_status"),
        "focus_cases": focus,
        "options": options,
        "separability": scan,
        "recommendation": _recommendation(options, scan),
    }


def render_report(payload: Mapping[str, object]) -> str:
    """Render the diagnosis markdown from ``build_diagnosis``."""
    rule = payload["product_rule"]
    baseline = payload["baseline"]
    focus = payload["focus_cases"]
    options = payload["options"]
    scan = payload["separability"]
    recommendation = payload["recommendation"]
    assert isinstance(rule, Mapping)
    assert isinstance(baseline, Mapping)
    assert isinstance(focus, list)
    assert isinstance(options, list)
    assert isinstance(scan, Mapping)
    assert isinstance(recommendation, Mapping)
    paraphrase = [case for case in focus if case["category"] == "paraphrase"]
    negatives = [case for case in focus if case["category"] in {"near_miss", "unsupported"}]
    lines = [
        "# Phase 4 status-gate diagnosis",
        "",
        "Diagnosis only. Product matching, hybrid weights, chunking, and models "
        "stay as they are. Scores are the recorded OpenAI semantic hybrid hits in "
        f"`{payload['source_results']}` "
        f"(`{payload['provider_name']}` / `{payload['model_name']}`, "
        f"{payload['ranking']}). This command does not embed new text.",
        "",
        "## Where status is decided",
        "",
        "The retrieval eval calls `EvidenceMatchService._match_requirement` with "
        "requirement kind `technology` and `top_k=3`. That path reaches "
        "`_evaluate_text` in `backend/app/features/resume_intelligence/matching.py`.",
        "",
        "Decision order:",
        "",
        "1. **Explicit phrase rules** run first. "
        f"`EXPLICIT_EVIDENCE_RULES` (line {rule['explicit_rules_line']}) covers "
        "AWS (`aws`, `amazon web services`, `amazon ec2`, `amazon s3`, `aws lambda`), "
        "Kubernetes (`kubernetes`, `k8s`), and CI/CD (`ci cd`, `continuous integration`, "
        "`continuous delivery`, `continuous deployment`). "
        f"`_evaluate_explicit_evidence` (line {rule['explicit_eval_line']}) scans the "
        "whole corpus for those aliases. Hybrid scores are not read. Status is "
        "`matched` only when every triggered rule has a chunk that contains the name "
        "or an accepted alias, `partially_matched` when only some of the triggered "
        "rules hit, and `not_evidenced` when none hit.",
        "2. **Citation filter** on the top 3: keep a chunk when `lexical_score > 0` or "
        f"`vector_score >= {_bar(VECTOR_CITATION_FLOOR)}` "
        f"(line {rule['citation_floor_line']}).",
        "3. **Matched** when a citation exists and either the normalized query is an "
        "exact substring of a citation or "
        f"`best_lexical >= {_bar(MATCHED_LEXICAL_BAR)}` "
        f"(line {rule['matched_lexical_line']}).",
        "4. **Partially matched** when a citation exists and "
        f"`best_lexical >= {_bar(PARTIAL_LEXICAL_BAR)}` "
        f"(line {rule['partial_lexical_line']}).",
        "5. **Not evidenced** when the citation list is empty or the best admitted "
        "lexical score is below 0.25.",
        "",
        f"The 0.65 figure is the single `Decimal(\"0.65\")` comparison in the matcher, "
        f"on line {rule['matched_lexical_line']}. It is `best_lexical` among admitted "
        "citations. The explicit-rule path returns before that line. An empty citation "
        "list returns `not_evidenced` before that line is evaluated.",
        "",
        "Lexical score is `|query tokens ∩ evidence tokens| / |query tokens|` after "
        "`normalize_text`. `retrieval_score` is the ranking combination "
        "`min(1, 0.7 * lexical + 0.3 * vector)`. `_evaluate_text` does not read "
        "`retrieval_score`. Stop-words are removed only by `_signal_tokens`, which "
        "decides `not_applicable`. They still count in the lexical score.",
        "",
        "## Paraphrase cases",
        "",
        "Expected status is `matched`. Scores below are the rank-1 chunk. "
        "Correct rank is the best relevant chunk in the full recorded ordering.",
        "",
        _case_table(paraphrase),
        "",
        _case_narratives(paraphrase),
        "## Near-miss and unsupported cases",
        "",
        "These ten cases have no relevant chunk. Correct rank is n/a. Scores are the "
        "rank-1 neighbor. Expected status is `not_evidenced`.",
        "",
        _case_table(negatives),
        "",
        _case_narratives(negatives),
        "## What the scores can separate",
        "",
        _separability_section(scan),
        "",
        "## Simulated options",
        "",
        "Both options are applied offline to the same recorded top 3. Explicit phrase "
        "rules stay in front and keep the product status. The current lexical matched "
        "path also stays. An option can only add `matched`. Product source is unchanged.",
        "",
    ]
    for option in options:
        assert isinstance(option, Mapping)
        lines.extend(_option_section(option))
    lines.extend(
        [
            "## Comparison",
            "",
            "| Option | Status accuracy | Paraphrase status | Unsupported FP | "
            "Near-miss FP | Cases that change |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            _metric_row("Current product gate", baseline),
        ]
    )
    for option in options:
        assert isinstance(option, Mapping)
        lines.append(_metric_row(str(option["name"]), option))
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"Choice: **{recommendation['choice']}**.",
            "",
            str(recommendation["text"]),
            "",
            "This recommendation is not implemented in product code.",
            "",
            "## How to reproduce",
            "",
            "```text",
            "cd backend",
            "python -m scripts.status_gate_diagnosis",
            "```",
            "",
            "The command rewrites `evals/results/status_gate_diagnosis.json` and "
            "`evals/results/status_gate_diagnosis.md` from `evals/results/results.json`. "
            "It does not read `OPENAI_API_KEY`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    payload: Mapping[str, object],
    *,
    json_path: Path | None = None,
    report_path: Path | None = None,
) -> None:
    """Write the machine-readable diagnosis and the markdown report."""
    json_path = json_path or DEFAULT_DIAGNOSIS_JSON
    report_path = report_path or DEFAULT_DIAGNOSIS_MARKDOWN
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")


def simulated_status(
    option_id: str,
    *,
    product_status: str,
    explicit: bool,
    hits: Sequence[Mapping[str, object]],
) -> str:
    """Apply one candidate gate without overriding an explicit phrase decision."""
    if explicit or product_status == MATCHED:
        return product_status
    if _promoting_hit(option_id, hits) is not None:
        return MATCHED
    return product_status


def main() -> None:
    """Write the diagnosis artifacts next to the frozen retrieval results."""
    payload = build_diagnosis()
    write_artifacts(payload)


def _openai_mode(payload: Mapping[str, object]) -> Mapping[str, object]:
    modes = payload.get("modes")
    if not isinstance(modes, Mapping):
        raise ValueError("results file has no modes")
    mode = modes.get("openai_semantic_hybrid")
    if not isinstance(mode, Mapping) or mode.get("ran") is not True:
        raise ValueError("recorded OpenAI semantic hybrid arm is missing")
    cases = mode.get("cases")
    if not isinstance(cases, list):
        raise ValueError("recorded OpenAI arm has no cases")
    if mode.get("model_name") != "text-embedding-3-small":
        raise ValueError("diagnosis expects the frozen text-embedding-3-small arm")
    return mode


def _diagnose_case(
    raw: Mapping[str, object],
    *,
    corpus: Corpus,
    provider: DeterministicHashEmbeddingProvider,
) -> dict[str, object]:
    if not isinstance(corpus, Corpus):
        raise TypeError("corpus must be the retrieval-eval corpus")
    case_id = str(raw["id"])
    query = str(raw["query"])
    category = str(raw["category"])
    expected = str(raw["expected_status"])
    recorded = str(raw["predicted_status"])
    relevant_keys = [str(key) for key in raw.get("relevant_keys", [])]
    relevant = set(relevant_keys)
    hits = _hits_for_case(raw, corpus=corpus, relevant=relevant, query=query)
    top3 = hits[:STATUS_TOP_K]
    ranked = [_retrieved(hit, corpus) for hit in top3]
    product_status = status_for_ranking(
        provider,
        corpus,
        query,
        ranked,
        case_id=case_id,
    )
    if product_status != recorded:
        raise ValueError(
            f"{case_id} replayed status {product_status} != recorded {recorded}"
        )
    explicit_rules = EvidenceMatchService._explicit_rules_for_requirement(query)
    explicit_status = _explicit_status(corpus, explicit_rules) if explicit_rules else None
    branch_status, rule_id, rule_text = _current_branch(
        query,
        top3,
        explicit_status=explicit_status,
        explicit_labels=tuple(label for label, _aliases in explicit_rules),
    )
    if branch_status != product_status:
        raise ValueError(
            f"{case_id} branch {rule_id} produced {branch_status}, "
            f"product returned {product_status}"
        )
    rank = raw.get("first_relevant_rank")
    correct_rank = int(rank) if isinstance(rank, int) else None
    return {
        "id": case_id,
        "category": category,
        "query": query,
        "expected_status": expected,
        "predicted_status": product_status,
        "status_correct": product_status == expected,
        "correct_evidence_rank": correct_rank,
        "explicit": bool(explicit_rules),
        "explicit_labels": [label for label, _aliases in explicit_rules],
        "top1": hits[0].as_dict() if hits else None,
        "top3": [hit.as_dict() for hit in top3],
        "first_relevant": _first_relevant(hits, correct_rank),
        "rule_id": rule_id,
        "rule": rule_text,
        "blocked_expected_status": product_status != expected,
        "relevant_outside_top_hits": [
            key for key in relevant_keys if key not in {hit.key for hit in hits}
        ],
    }


def _hits_for_case(
    raw: Mapping[str, object],
    *,
    corpus: Corpus,
    relevant: set[str],
    query: str,
) -> list[Hit]:
    if not isinstance(corpus, Corpus):
        raise TypeError("corpus must be the retrieval-eval corpus")
    raw_hits = raw.get("top_hits")
    if not isinstance(raw_hits, list) or len(raw_hits) < STATUS_TOP_K:
        raise ValueError(f"{raw.get('id')} is missing recorded top hits")
    query_tokens = set(normalize_text(query).split())
    hits: list[Hit] = []
    for item in raw_hits:
        if not isinstance(item, Mapping):
            raise ValueError(f"{raw.get('id')} has a malformed hit")
        key = str(item["key"])
        evidence = corpus.by_key[key]
        overlap = tuple(sorted(query_tokens & set(normalize_text(evidence.text).split())))
        lexical = _recorded_decimal(item["lexical_score"])
        recomputed = _quantize(
            Decimal(len(overlap)) / Decimal(len(query_tokens)) if query_tokens else Decimal("0")
        )
        if recomputed != lexical:
            raise ValueError(
                f"{raw.get('id')} {key} lexical {lexical} != recomputed {recomputed} "
                f"from overlap {list(overlap)}"
            )
        hits.append(
            Hit(
                rank=int(item["rank"]),
                key=key,
                lexical_score=lexical,
                vector_score=_recorded_decimal(item["vector_score"]),
                combined_score=_recorded_decimal(item["retrieval_score"]),
                text=evidence.text,
                overlap_tokens=overlap,
                relevant=key in relevant,
            )
        )
    return hits


def _retrieved(hit: Hit, corpus: Corpus) -> RetrievedCandidateEvidence:
    if not isinstance(corpus, Corpus):
        raise TypeError("corpus must be the retrieval-eval corpus")
    evidence = corpus.by_key[hit.key]
    return RetrievedCandidateEvidence(
        **evidence.model_dump(),
        retrieval_score=hit.combined_score,
        lexical_score=hit.lexical_score,
        vector_score=hit.vector_score,
        why_retrieved="Recorded OpenAI semantic hybrid score.",
    )


def _explicit_status(corpus: Corpus, rules: list[tuple[str, tuple[str, ...]]]) -> str:
    if not isinstance(corpus, Corpus):
        raise TypeError("corpus must be the retrieval-eval corpus")
    service = EvidenceMatchService.__new__(EvidenceMatchService)
    service.retriever = CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider())
    status, _citations = service._evaluate_explicit_evidence(corpus.candidate, rules)
    return status.value


def _current_branch(
    query: str,
    hits: Sequence[Hit],
    *,
    explicit_status: str | None,
    explicit_labels: tuple[str, ...],
) -> tuple[str, str, str]:
    """Mirror `_evaluate_text` and name the branch that produced the status."""
    if explicit_status is not None:
        labels = ", ".join(explicit_labels)
        top = hits[0]
        if explicit_status == NOT_EVIDENCED:
            rule_id = "explicit_phrase_absent"
            text = (
                f"Query triggers explicit phrase rule {labels}. "
                "`_evaluate_explicit_evidence` found no corpus chunk with the required "
                "alias, so status is not_evidenced. Hybrid scores are not consulted. "
                f"Rank-1 neighbor is {top.key} at lexical {_fmt(top.lexical_score)}, "
                f"vector {_fmt(top.vector_score)}, combined {_fmt(top.combined_score)} "
                f"(overlap {list(top.overlap_tokens) or 'none'})."
            )
        elif explicit_status == MATCHED:
            rule_id = "explicit_phrase_matched"
            text = f"Explicit phrase rule {labels} matched a corpus alias."
        else:
            rule_id = "explicit_phrase_partial"
            text = f"Explicit phrase rule {labels} matched only part of the required aliases."
        return explicit_status, rule_id, text

    if not EvidenceMatchService._signal_tokens(query):
        return (
            NOT_APPLICABLE,
            "no_signal_tokens",
            "The query has no evidence signal token, so status is not_applicable.",
        )

    citations = [
        hit
        for hit in hits
        if hit.lexical_score > 0 or hit.vector_score >= VECTOR_CITATION_FLOOR
    ]
    best_lexical = max((hit.lexical_score for hit in citations), default=Decimal("0"))
    exact = any(normalize_text(query) in normalize_text(hit.text) for hit in citations)
    if citations and (exact or best_lexical >= MATCHED_LEXICAL_BAR):
        deciding = max(citations, key=lambda hit: (hit.lexical_score, hit.vector_score, -hit.rank))
        rule_id = "lexical_matched_bar"
        exact_note = " The normalized query is also an exact substring." if exact else ""
        text = (
            f"best lexical {_fmt(deciding.lexical_score)} on {deciding.key} "
            f"(overlap {list(deciding.overlap_tokens) or 'none'}) meets the "
            f"{_bar(MATCHED_LEXICAL_BAR)} matched bar.{exact_note}"
        )
        return MATCHED, rule_id, text
    if citations and best_lexical >= PARTIAL_LEXICAL_BAR:
        deciding = max(citations, key=lambda hit: (hit.lexical_score, hit.vector_score, -hit.rank))
        tied = [
            hit
            for hit in citations
            if hit.lexical_score == deciding.lexical_score
        ]
        overlap_note = "; ".join(
            f"{hit.key} overlap {list(hit.overlap_tokens) or 'none'}" for hit in tied
        )
        text = (
            f"Admitted citations have best lexical {_fmt(best_lexical)} "
            f"({overlap_note}). That is below the {_bar(MATCHED_LEXICAL_BAR)} matched "
            f"bar and at least the {_bar(PARTIAL_LEXICAL_BAR)} partial bar, so status "
            "is partially_matched. The normalized query is not an exact substring of "
            "an admitted citation."
        )
        return PARTIAL, "lexical_partial_below_matched_bar", text
    top = hits[0]
    max_vector = max(hit.vector_score for hit in hits)
    if not citations:
        text = (
            "No top-3 chunk was admitted. Admission requires lexical_score > 0 or "
            f"vector_score >= {_bar(VECTOR_CITATION_FLOOR)}. Rank-1 {top.key} has "
            f"lexical {_fmt(top.lexical_score)} and vector {_fmt(top.vector_score)}. "
            f"The highest top-3 vector is {_fmt(max_vector)}. `_evaluate_text` returns "
            "not_evidenced on the empty citation list, before the "
            f"{_bar(MATCHED_LEXICAL_BAR)} lexical bar is evaluated."
        )
        return NOT_EVIDENCED, "citation_filter_empty", text
    text = (
        f"Citations were admitted, and best lexical {_fmt(best_lexical)} is below the "
        f"{_bar(PARTIAL_LEXICAL_BAR)} partial bar, so status is not_evidenced."
    )
    return NOT_EVIDENCED, "lexical_below_partial_bar", text


def _promoting_hit(
    option_id: str,
    hits: Sequence[Mapping[str, object]],
) -> Mapping[str, object] | None:
    if option_id == OPTION_VECTOR:
        eligible = [
            hit
            for hit in hits
            if _decimal(hit["vector_score"]) >= OPTION_VECTOR_MATCH_BAR
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda hit: (_decimal(hit["vector_score"]), -int(hit["rank"])))
    if option_id == OPTION_PARTIAL:
        eligible = [
            hit
            for hit in hits
            if _decimal(hit["lexical_score"]) >= PARTIAL_LEXICAL_BAR
            and _decimal(hit["vector_score"]) >= OPTION_PARTIAL_VECTOR_BAR
        ]
        if not eligible:
            return None
        return max(
            eligible,
            key=lambda hit: (
                _decimal(hit["vector_score"]),
                _decimal(hit["lexical_score"]),
                -int(hit["rank"]),
            ),
        )
    raise ValueError(f"unknown gate option {option_id}")


def _simulate_option(option_id: str, cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    changed: list[dict[str, object]] = []
    projected: list[dict[str, object]] = []
    for case in cases:
        hits = case["top3"]
        assert isinstance(hits, list)
        product_status = str(case["predicted_status"])
        status = simulated_status(
            option_id,
            product_status=product_status,
            explicit=bool(case["explicit"]),
            hits=hits,
        )
        projected.append({**case, "predicted_status": status})
        if status != product_status:
            promoter = _promoting_hit(option_id, hits)
            assert promoter is not None
            changed.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "from": product_status,
                    "to": status,
                    "chunk": promoter["key"],
                    "lexical_score": _fmt(_decimal(promoter["lexical_score"])),
                    "vector_score": _fmt(_decimal(promoter["vector_score"])),
                    "combined_score": _fmt(_decimal(promoter["combined_score"])),
                }
            )
    metrics = _metrics(projected, status_key="predicted_status")
    return {
        "id": option_id,
        "name": _option_name(option_id),
        "definition": _option_definition(option_id),
        **metrics,
        "changed_cases": changed,
    }


def _metrics(cases: Sequence[Mapping[str, object]], *, status_key: str) -> dict[str, object]:
    paraphrase = [case for case in cases if case["category"] == "paraphrase"]
    status_hits = sum(int(case[status_key] == case["expected_status"]) for case in cases)
    paraphrase_hits = sum(
        int(case[status_key] == case["expected_status"]) for case in paraphrase
    )
    unsupported_ids = [
        str(case["id"])
        for case in cases
        if is_unsupported_false_positive(
            str(case["category"]),
            str(case["expected_status"]),
            str(case[status_key]),
        )
    ]
    near_ids = [
        str(case["id"])
        for case in cases
        if is_near_miss_false_positive(
            str(case["category"]),
            str(case["expected_status"]),
            str(case[status_key]),
        )
    ]
    unsupported_cases = sum(int(case["category"] == "unsupported") for case in cases)
    near_cases = sum(int(case["category"] == "near_miss") for case in cases)
    return {
        "status_accuracy": {"hits": status_hits, "cases": len(cases)},
        "paraphrase_status_accuracy": {"hits": paraphrase_hits, "cases": len(paraphrase)},
        "unsupported_false_positives": {
            "count": len(unsupported_ids),
            "cases": unsupported_cases,
            "case_ids": unsupported_ids,
        },
        "near_miss_false_positives": {
            "count": len(near_ids),
            "cases": near_cases,
            "case_ids": near_ids,
        },
    }


def _vector_separability(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Show which absolute vector cuts accept para-ocr and which neighbors they catch."""
    by_id = {str(case["id"]): case for case in cases}
    ocr_vector = _max_vector(by_id["para-ocr"])
    negatives = [
        case
        for case in cases
        if case["category"] in {"near_miss", "unsupported"}
    ]
    caught_with_explicit_held = [
        str(case["id"])
        for case in negatives
        if not case["explicit"] and _max_vector(case) >= ocr_vector
    ]
    strongest_non_explicit = max(
        (case for case in negatives if not case["explicit"]),
        key=_max_vector,
    )
    band_floor = _max_vector(strongest_non_explicit)
    paraphrase_inside_band = [
        str(case["id"])
        for case in cases
        if case["category"] == "paraphrase" and _max_vector(case) > band_floor
    ]
    above_floor = [
        str(case["id"])
        for case in cases
        if case["category"] == "paraphrase" and _max_vector(case) >= VECTOR_CITATION_FLOOR
    ]
    return {
        "para_ocr_max_top3_vector": _fmt(ocr_vector),
        "non_explicit_negatives_at_or_above_para_ocr": caught_with_explicit_held,
        "strongest_non_explicit_negative": {
            "id": strongest_non_explicit["id"],
            "vector": _fmt(_max_vector(strongest_non_explicit)),
        },
        "zero_fp_vector_band_exclusive_floor": _fmt(band_floor),
        "paraphrase_cases_above_that_floor": paraphrase_inside_band,
        "paraphrase_cases_at_or_above_citation_floor_0_45": above_floor,
        "near_cicd_max_top3_vector": _fmt(_max_vector(by_id["near-cicd"])),
        "near_django_max_top3_vector": _fmt(_max_vector(by_id["near-django"])),
        "unsup_salesforce_max_top3_vector": _fmt(_max_vector(by_id["unsup-salesforce"])),
        "unsup_aws_max_top3_vector": _fmt(_max_vector(by_id["unsup-aws"])),
        "unsup_aws_max_top3_lexical": _fmt(_max_lexical(by_id["unsup-aws"])),
    }


def _recommendation(
    options: Sequence[Mapping[str, object]],
    scan: Mapping[str, object],
) -> dict[str, str]:
    by_id = {str(option["id"]): option for option in options}
    vector_option = by_id[OPTION_VECTOR]
    partial_option = by_id[OPTION_PARTIAL]
    ocr_blockers = ", ".join(
        f"`{case_id}`" for case_id in scan["non_explicit_negatives_at_or_above_para_ocr"]
    )
    vector_changes = _change_phrase(vector_option["changed_cases"])
    partial_changes = _change_phrase(partial_option["changed_cases"])
    text = " ".join(
        [
            "Leave the product status gate unchanged.",
            "The measured miss that retrieval already ranked correctly is `para-ocr`: "
            "relevant evidence is rank 1 with lexical 0.0000 and vector "
            f"{scan['para_ocr_max_top3_vector']}. Both simulated options leave that "
            "case `not_evidenced`.",
            "An absolute vector cut low enough to admit that "
            f"{scan['para_ocr_max_top3_vector']} score also admits "
            f"{ocr_blockers} on this frozen run "
            f"(Django vector {scan['near_django_max_top3_vector']}, "
            f"Salesforce vector {scan['unsup_salesforce_max_top3_vector']}), "
            "even while the AWS, Kubernetes, and CI/CD phrase rules stay in front.",
            f"The 0.42 vector bar moves {vector_changes}. "
            "The accepted Docker skill vector is 0.4279 and the CI/CD neighbor on "
            f"`skill:Docker` is {scan['near_cicd_max_top3_vector']}. "
            "That gap is too small to add a new constant from one 24-case run.",
            f"The same-chunk partial confirmation moves {partial_changes}. "
            "It still misses `para-ocr` and `para-sql-expansion`. "
            "`unsup-aws` would satisfy the same numeric test "
            f"(lexical {scan['unsup_aws_max_top3_lexical']}, "
            f"vector {scan['unsup_aws_max_top3_vector']}) if the explicit AWS phrase "
            "rule did not return first.",
            "Unsupported false positives stay 0/5 and near-miss false positives stay "
            "0/5 under both options. Those safe counts do not repair the rank-correct "
            "zero-lexical miss, so neither rule is worth implementing yet.",
        ]
    )
    return {"choice": "leave_unchanged", "text": text}


def _product_rule_description() -> dict[str, object]:
    source = Path(inspect.getfile(EvidenceMatchService)).read_text(encoding="utf-8")
    return {
        "module": "app.features.resume_intelligence.matching",
        "function": "EvidenceMatchService._evaluate_text",
        "explicit_rules_line": _line_containing(source, "EXPLICIT_EVIDENCE_RULES:"),
        "explicit_eval_line": inspect.getsourcelines(
            EvidenceMatchService._evaluate_explicit_evidence
        )[1],
        "evaluate_text_line": inspect.getsourcelines(EvidenceMatchService._evaluate_text)[1],
        "citation_floor_line": _line_containing(source, 'vector_score >= Decimal("0.45")'),
        "matched_lexical_line": _line_containing(source, 'best_lexical >= Decimal("0.65")'),
        "partial_lexical_line": _line_containing(source, 'best_lexical >= Decimal("0.25")'),
        "matched_lexical_bar": _fmt(MATCHED_LEXICAL_BAR),
        "partial_lexical_bar": _fmt(PARTIAL_LEXICAL_BAR),
        "vector_citation_floor": _fmt(VECTOR_CITATION_FLOOR),
        "explicit_rules": {
            label: list(aliases) for label, aliases in EXPLICIT_EVIDENCE_RULES.items()
        },
        "status_top_k": STATUS_TOP_K,
        "hybrid_weights": "lexical 0.7 / vector 0.3, ranking only",
    }


def _case_table(cases: Sequence[object]) -> str:
    header = (
        "| Case | Top-1 evidence | Lexical | Vector | Combined | Correct rank | "
        "Status | Rule |"
    )
    separator = "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |"
    rows = [header, separator]
    for case in cases:
        assert isinstance(case, Mapping)
        top1 = case["top1"]
        assert isinstance(top1, Mapping)
        rank = case["correct_evidence_rank"]
        rank_text = "n/a" if rank is None else str(rank)
        rows.append(
            "| "
            + " | ".join(
                [
                    str(case["id"]),
                    str(top1["key"]),
                    str(top1["lexical_score"]),
                    str(top1["vector_score"]),
                    str(top1["combined_score"]),
                    rank_text,
                    f"{case['predicted_status']} (expected {case['expected_status']})",
                    str(case["rule_id"]),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _case_narratives(cases: Sequence[object]) -> str:
    blocks: list[str] = []
    for case in cases:
        assert isinstance(case, Mapping)
        relevant = case["first_relevant"]
        extra = ""
        top1 = case["top1"]
        assert isinstance(top1, Mapping)
        if isinstance(relevant, Mapping) and relevant.get("key") != top1.get("key"):
            extra = (
                f" First relevant chunk is rank {relevant['rank']} {relevant['key']} "
                f"(lexical {relevant['lexical_score']}, vector {relevant['vector_score']}, "
                f"combined {relevant['combined_score']})."
            )
        outcome = (
            "This rule blocked the expected status."
            if case["blocked_expected_status"]
            else "This rule produced the expected status."
        )
        excluded = _excluded_relevant_note(case)
        missing = case.get("relevant_outside_top_hits") or []
        missing_note = ""
        if missing:
            listed = ", ".join(f"`{key}`" for key in missing)
            missing_note = f" Labeled relevant evidence outside the recorded top 5: {listed}."
        blocks.append(
            f"### {case['id']}\n\n{case['rule']}{extra}{excluded}{missing_note} {outcome}\n"
        )
    return "\n".join(blocks)


def _separability_section(scan: Mapping[str, object]) -> str:
    caught = ", ".join(
        f"`{case_id}`" for case_id in scan["non_explicit_negatives_at_or_above_para_ocr"]
    )
    inside = ", ".join(f"`{case_id}`" for case_id in scan["paraphrase_cases_above_that_floor"])
    above = scan["paraphrase_cases_at_or_above_citation_floor_0_45"]
    above_text = "none" if not above else ", ".join(f"`{case_id}`" for case_id in above)
    return "\n".join(
        [
            f"`para-ocr` rank 1 vector is {scan['para_ocr_max_top3_vector']}. "
            f"The non-explicit negatives at or above that vector are {caught}. "
            "A vector matched bar low enough to accept `para-ocr` therefore adds "
            "near-miss and unsupported false positives on this run.",
            "",
            "Among negatives that do not trigger an explicit phrase rule, the "
            f"strongest top-3 vector is {scan['zero_fp_vector_band_exclusive_floor']} "
            f"on `{scan['strongest_non_explicit_negative']['id']}`. "
            "A vector matched bar above that score adds no near-miss or unsupported "
            f"false positive on this run. Paraphrase cases above it: {inside}.",
            "",
            "The existing 0.45 citation floor is above every paraphrase top-3 vector "
            f"in this arm ({above_text}). `para-human-approval` reaches 0.4406 and "
            "`para-containers` `skill:Docker` reaches 0.4279. Lowering the citation "
            "floor by itself does not change status, because after admission the "
            "matched decision still requires an exact substring or lexical score "
            ">= 0.65.",
        ]
    )


def _option_section(option: Mapping[str, object]) -> list[str]:
    changes = option["changed_cases"]
    assert isinstance(changes, list)
    if changes:
        change_lines = [
            f"- `{item['id']}`: {item['from']} -> {item['to']} via {item['chunk']} "
            f"(lexical {item['lexical_score']}, vector {item['vector_score']}, "
            f"combined {item['combined_score']})"
            for item in changes
            if isinstance(item, Mapping)
        ]
    else:
        change_lines = ["- None."]
    return [
        f"### {option['name']}",
        "",
        str(option["definition"]),
        "",
        "Cases that change:",
        "",
        *change_lines,
        "",
    ]


def _metric_row(name: str, metrics: Mapping[str, object]) -> str:
    status = metrics["status_accuracy"]
    paraphrase = metrics["paraphrase_status_accuracy"]
    unsupported = metrics["unsupported_false_positives"]
    near = metrics["near_miss_false_positives"]
    assert isinstance(status, Mapping)
    assert isinstance(paraphrase, Mapping)
    assert isinstance(unsupported, Mapping)
    assert isinstance(near, Mapping)
    changes = metrics.get("changed_cases")
    if isinstance(changes, list):
        change_text = ", ".join(str(item["id"]) for item in changes if isinstance(item, Mapping))
        change_text = change_text or "none"
    else:
        change_text = "—"
    return (
        f"| {name} | {_ratio(status)} | {_ratio(paraphrase)} | "
        f"{unsupported['count']}/{unsupported['cases']} | "
        f"{near['count']}/{near['cases']} | {change_text} |"
    )


def _option_name(option_id: str) -> str:
    if option_id == OPTION_VECTOR:
        return "Option A: top-3 vector matched bar (0.42)"
    if option_id == OPTION_PARTIAL:
        return "Option B: same-chunk partial confirmation (lexical 0.25 and vector 0.30)"
    raise ValueError(option_id)


def _option_definition(option_id: str) -> str:
    if option_id == OPTION_VECTOR:
        return (
            "After the explicit phrase rules and the current matched conditions "
            "(exact substring or lexical >= 0.65), also mark `matched` when any "
            "top-3 chunk has vector_score >= 0.42. 0.42 sits inside the measured "
            "zero-false-positive band: above Salesforce 0.3527 and CI/CD's Docker "
            "neighbor 0.3974, and still at or below `para-containers` skill:Docker "
            "0.4279 and `para-human-approval` 0.4406."
        )
    if option_id == OPTION_PARTIAL:
        return (
            "After the explicit phrase rules and the current matched conditions, "
            "also mark `matched` when one top-3 chunk has lexical_score >= 0.25 "
            "and vector_score >= 0.30. The lexical floor is the existing partial "
            "bar. The vector floor sits below `para-relational-databases` skill:SQL "
            "0.3413 and `para-human-approval` 0.4406, and above the incidental "
            "partials `para-sql-expansion` 0.2078 and the `para-containers` "
            "\"system\" overlap 0.2318. Lexical and vector must come from the same chunk."
        )
    raise ValueError(option_id)


def _excluded_relevant_note(case: Mapping[str, object]) -> str:
    """Name relevant top-3 chunks the citation filter dropped."""
    hits = case["top3"]
    if not isinstance(hits, list):
        return ""
    dropped = [
        hit
        for hit in hits
        if isinstance(hit, Mapping)
        and hit.get("relevant") is True
        and _decimal(hit["lexical_score"]) == 0
        and _decimal(hit["vector_score"]) < VECTOR_CITATION_FLOOR
    ]
    if not dropped:
        return ""
    pieces = [
        (
            f"`{hit['key']}` is rank {hit['rank']} with lexical {hit['lexical_score']} "
            f"and vector {hit['vector_score']}"
        )
        for hit in dropped
    ]
    return (
        " Relevant evidence the citation filter excluded: "
        + "; ".join(pieces)
        + f". Vector is below {_bar(VECTOR_CITATION_FLOOR)} and lexical is 0, "
        "so those chunks do not enter the 0.65 comparison."
    )


def _bar(value: Decimal) -> str:
    return f"{value:.2f}"


def _first_relevant(hits: Sequence[Hit], rank: int | None) -> dict[str, object] | None:
    if rank is None:
        return None
    for hit in hits:
        if hit.relevant and hit.rank == rank:
            return hit.as_dict()
    return {"rank": rank, "key": None, "note": "outside the recorded top hits"}


def _max_vector(case: Mapping[str, object]) -> Decimal:
    hits = case["top3"]
    assert isinstance(hits, list)
    return max(_decimal(hit["vector_score"]) for hit in hits if isinstance(hit, Mapping))


def _max_lexical(case: Mapping[str, object]) -> Decimal:
    hits = case["top3"]
    assert isinstance(hits, list)
    return max(_decimal(hit["lexical_score"]) for hit in hits if isinstance(hit, Mapping))


def _change_phrase(changes: object) -> str:
    if not isinstance(changes, list) or not changes:
        return "no cases"
    parts = [
        f"`{item['id']}` ({item['from']} -> {item['to']})"
        for item in changes
        if isinstance(item, Mapping)
    ]
    return ", ".join(parts)


def _ratio(metric: Mapping[str, object]) -> str:
    return f"{metric['hits']}/{metric['cases']}"


def _recorded_decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise TypeError("recorded scores must be strings from results.json")
    return Decimal(value)


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError("score must be a Decimal or a recorded decimal string")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}"


def _line_containing(source: str, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    raise ValueError(f"could not find {needle!r} in EvidenceMatchService")


if __name__ == "__main__":
    main()
