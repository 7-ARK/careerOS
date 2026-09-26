"""Offline status-gate diagnosis. No live OpenAI calls."""

import inspect
import json
from pathlib import Path

from app.features.resume_intelligence.matching import EvidenceMatchService
from scripts.status_gate_diagnosis import (
    DEFAULT_DIAGNOSIS_JSON,
    DEFAULT_DIAGNOSIS_MARKDOWN,
    OPTION_PARTIAL,
    OPTION_VECTOR,
    build_diagnosis,
    render_report,
    simulated_status,
)

RESULTS = Path(__file__).parents[2] / "evals" / "results" / "results.json"


def test_replay_names_the_recorded_openai_gate_branch() -> None:
    payload = build_diagnosis(RESULTS)
    baseline = payload["baseline"]
    assert baseline["status_accuracy"] == {"hits": 19, "cases": 24}
    assert baseline["paraphrase_status_accuracy"] == {"hits": 1, "cases": 6}
    assert baseline["unsupported_false_positives"]["count"] == 0
    assert baseline["near_miss_false_positives"]["count"] == 0
    assert payload["model_name"] == "text-embedding-3-small"

    rules = {case["id"]: case["rule_id"] for case in payload["focus_cases"]}
    assert rules["para-ocr"] == "citation_filter_empty"
    assert rules["para-sql-expansion"] == "lexical_partial_below_matched_bar"
    assert rules["para-containers"] == "lexical_partial_below_matched_bar"
    assert rules["para-python-web-framework"] == "lexical_matched_bar"
    assert rules["para-human-approval"] == "lexical_partial_below_matched_bar"
    assert rules["para-relational-databases"] == "lexical_partial_below_matched_bar"
    assert rules["near-kubernetes"] == "explicit_phrase_absent"
    assert rules["near-cicd"] == "explicit_phrase_absent"
    assert rules["near-django"] == "citation_filter_empty"
    assert rules["unsup-aws"] == "explicit_phrase_absent"
    assert rules["unsup-salesforce"] == "citation_filter_empty"
    assert rules["unsup-terraform"] == "citation_filter_empty"

    ocr = next(case for case in payload["focus_cases"] if case["id"] == "para-ocr")
    assert ocr["correct_evidence_rank"] == 1
    assert ocr["top1"]["lexical_score"] == "0.0000"
    assert ocr["top1"]["vector_score"] == "0.3141"
    assert ocr["top1"]["combined_score"] == "0.0942"
    assert ocr["blocked_expected_status"] is True

    containers = next(case for case in payload["focus_cases"] if case["id"] == "para-containers")
    docker = next(hit for hit in containers["top3"] if hit["key"] == "skill:Docker")
    assert docker["lexical_score"] == "0.0000"
    assert docker["vector_score"] == "0.4279"
    assert "skill:SQL" in next(
        case["relevant_outside_top_hits"]
        for case in payload["focus_cases"]
        if case["id"] == "para-sql-expansion"
    )


def test_options_improve_two_paraphrase_labels_without_false_positives() -> None:
    payload = build_diagnosis(RESULTS)
    options = {option["id"]: option for option in payload["options"]}
    vector = options[OPTION_VECTOR]
    partial = options[OPTION_PARTIAL]

    assert vector["status_accuracy"] == {"hits": 21, "cases": 24}
    assert vector["paraphrase_status_accuracy"] == {"hits": 3, "cases": 6}
    assert vector["unsupported_false_positives"] == {"count": 0, "cases": 5, "case_ids": []}
    assert vector["near_miss_false_positives"] == {"count": 0, "cases": 5, "case_ids": []}
    assert [item["id"] for item in vector["changed_cases"]] == [
        "para-containers",
        "para-human-approval",
    ]
    assert vector["changed_cases"][0]["chunk"] == "skill:Docker"
    assert vector["changed_cases"][0]["vector_score"] == "0.4279"

    assert partial["status_accuracy"] == {"hits": 21, "cases": 24}
    assert partial["paraphrase_status_accuracy"] == {"hits": 3, "cases": 6}
    assert partial["unsupported_false_positives"]["count"] == 0
    assert partial["near_miss_false_positives"]["count"] == 0
    assert [item["id"] for item in partial["changed_cases"]] == [
        "para-human-approval",
        "para-relational-databases",
    ]
    assert partial["changed_cases"][1]["chunk"] == "skill:SQL"

    scan = payload["separability"]
    assert scan["non_explicit_negatives_at_or_above_para_ocr"] == [
        "near-django",
        "unsup-salesforce",
    ]
    assert scan["paraphrase_cases_at_or_above_citation_floor_0_45"] == []
    assert payload["recommendation"]["choice"] == "leave_unchanged"
    report = render_report(payload)
    assert "para-ocr" in report
    assert "leave_unchanged" in report
    assert "21/24" in report
    assert "3/6" in report


def test_simulated_status_does_not_override_explicit_rules_or_low_vectors() -> None:
    docker = [
        {
            "rank": 3,
            "key": "skill:Docker",
            "lexical_score": "0.0000",
            "vector_score": "0.4279",
            "combined_score": "0.1284",
        }
    ]
    assert (
        simulated_status(
            OPTION_VECTOR,
            product_status="partially_matched",
            explicit=False,
            hits=docker,
        )
        == "matched"
    )
    assert (
        simulated_status(
            OPTION_PARTIAL,
            product_status="partially_matched",
            explicit=False,
            hits=docker,
        )
        == "partially_matched"
    )

    cicd = [
        {
            "rank": 1,
            "key": "skill:Docker",
            "lexical_score": "0.0000",
            "vector_score": "0.3974",
            "combined_score": "0.1192",
        }
    ]
    assert (
        simulated_status(
            OPTION_VECTOR,
            product_status="not_evidenced",
            explicit=True,
            hits=cicd,
        )
        == "not_evidenced"
    )

    aws = [
        {
            "rank": 1,
            "key": "profile",
            "lexical_score": "0.3333",
            "vector_score": "0.3602",
            "combined_score": "0.3414",
        }
    ]
    assert (
        simulated_status(
            OPTION_PARTIAL,
            product_status="not_evidenced",
            explicit=True,
            hits=aws,
        )
        == "not_evidenced"
    )
    assert (
        simulated_status(
            OPTION_PARTIAL,
            product_status="not_evidenced",
            explicit=False,
            hits=aws,
        )
        == "matched"
    )

    salesforce = [
        {
            "rank": 1,
            "key": "experience:Northstar Digital Studio",
            "lexical_score": "0.0000",
            "vector_score": "0.3527",
            "combined_score": "0.1058",
        }
    ]
    assert (
        simulated_status(
            OPTION_VECTOR,
            product_status="not_evidenced",
            explicit=False,
            hits=salesforce,
        )
        == "not_evidenced"
    )

    ocr = [
        {
            "rank": 1,
            "key": "project:Legal Document OCR and Extraction System",
            "lexical_score": "0.0000",
            "vector_score": "0.3141",
            "combined_score": "0.0942",
        }
    ]
    assert (
        simulated_status(OPTION_VECTOR, product_status="not_evidenced", explicit=False, hits=ocr)
        == "not_evidenced"
    )
    assert (
        simulated_status(OPTION_PARTIAL, product_status="not_evidenced", explicit=False, hits=ocr)
        == "not_evidenced"
    )
    assert (
        simulated_status(OPTION_VECTOR, product_status="matched", explicit=False, hits=ocr)
        == "matched"
    )


def test_committed_diagnosis_matches_the_replay() -> None:
    payload = build_diagnosis(RESULTS)
    committed = json.loads(DEFAULT_DIAGNOSIS_JSON.read_text(encoding="utf-8"))
    assert committed == payload
    assert DEFAULT_DIAGNOSIS_MARKDOWN.read_text(encoding="utf-8") == render_report(payload)


def test_product_matcher_thresholds_stay_in_place() -> None:
    source = Path(inspect.getfile(EvidenceMatchService)).read_text(encoding="utf-8")
    diagnosis = Path(inspect.getfile(build_diagnosis)).read_text(encoding="utf-8")
    assert source.count('Decimal("0.65")') == 1
    assert 'vector_score >= Decimal("0.45")' in source
    assert 'best_lexical >= Decimal("0.25")' in source
    assert "OpenAIEmbeddingProvider(" not in diagnosis
