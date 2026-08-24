"""Executable expectations for the three deterministic recruiter fixtures."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.features.job_analysis import RuleBasedJobAnalyzer
from app.features.resume_intelligence.retrieval import (
    DeterministicHashEmbeddingProvider,
    LocalVectorStore,
    normalize_text,
)
from app.schemas import CandidateEvidence, JobDescriptionInput

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "evals" / "fixtures"
FIXTURE_PATHS = sorted(FIXTURE_DIRECTORY.glob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_recruiter_fixture_structured_output_and_retrieval(fixture_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    job = fixture["job"]
    analysis = RuleBasedJobAnalyzer().analyze(
        JobDescriptionInput(
            raw_title=job["title"],
            company_name=job["company"],
            description_text=job["description"],
        )
    )
    extracted = {
        *analysis.required_skills,
        *analysis.preferred_skills,
        *analysis.required_technologies,
        *analysis.preferred_technologies,
    }
    assert set(fixture["expected_extracted_terms"]).issubset(extracted)

    evidence = [
        CandidateEvidence(
            evidence_id=item["evidence_id"],
            source_id=uuid5(NAMESPACE_URL, item["evidence_id"]),
            category=item["category"],
            text=item["text"],
        )
        for item in fixture["evidence"]
    ]
    store = LocalVectorStore(DeterministicHashEmbeddingProvider())
    store.index(evidence)
    for query, expected_evidence_id in fixture["expected_retrieval"].items():
        retrieved = store.search(query, top_k=1)
        assert retrieved[0].evidence_id == expected_evidence_id
        assert retrieved[0].retrieval_score > 0

    evidence_text = normalize_text(" ".join(item.text for item in evidence))
    for missing in fixture["expected_missing_requirements"]:
        assert normalize_text(missing) not in evidence_text
    for unsupported_claim in fixture["unsupported_claims_to_reject"]:
        assert normalize_text(unsupported_claim) not in evidence_text
