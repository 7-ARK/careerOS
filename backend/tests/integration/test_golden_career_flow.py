"""Integration coverage for the recruiter-facing golden career-analysis flow."""

import tempfile
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.dependencies import get_db, get_golden_career_analysis_service
from app.features.document_generation import DocumentGenerationService
from app.features.resume_intelligence.retrieval import (
    DeterministicHashEmbeddingProvider,
    build_embedding_provider,
)
from app.main import app
from app.models import CareerAnalysisRun, ResumeDraft
from app.models.enums import CareerAnalysisStatus
from app.services.career_analysis import GoldenCareerAnalysisService
from app.services.job_import import ManualJobImportService
from tests.support import create_test_engine, create_test_session


@pytest.fixture
def golden_client() -> Iterator[tuple[TestClient, Session, Path]]:
    """Provide an isolated authenticated API database and local export directory."""
    engine = create_test_engine()
    session = create_test_session(engine)
    temporary_directory = tempfile.TemporaryDirectory()
    output_directory = Path(temporary_directory.name)
    service = GoldenCareerAnalysisService(session)
    service.document_generation = DocumentGenerationService(
        session,
        output_directory=output_directory,
    )

    def override_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_golden_career_analysis_service] = lambda: service
    try:
        yield TestClient(app), session, output_directory
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()
        temporary_directory.cleanup()


def test_golden_flow_requires_review_then_exports_and_tracks(
    golden_client: tuple[TestClient, Session, Path],
) -> None:
    client, _session, output_directory = golden_client
    headers, candidate_id = _authenticated_candidate(client)

    started = client.post(
        "/api/v1/career-analyses",
        headers=headers,
        json=_golden_request(candidate_id),
    )
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["status"] == "awaiting_review"
    assert run["current_stage"] == "human_review"
    assert run["provider"] == "deterministic_local"
    assert run["model_name"] == "feature-hash-v1"
    assert run["token_usage"] == {}
    assert Decimal(run["estimated_cost_usd"]) == 0
    assert run["generated_documents"] == []
    assert run["resume_draft"]["status"] == "draft"
    assert run["application_record"] is None
    assert run["application_record_id"] is None
    assert run["grounding_validation"]["valid"] is True
    assert run["grounding_validation"]["citation_coverage"] == "100.00"
    assert any(stage["status"] == "awaiting_review" for stage in run["stages"])

    history = client.get(
        f"/api/v1/career-analyses/candidate/{candidate_id}",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert [item["id"] for item in history.json()] == [run["id"]]

    explanation = run["match_explanation"]
    assert explanation["evidence_coverage"]["formula"].startswith(
        "100 * earned weight / possible weight"
    )
    python_match = next(
        match
        for match in explanation["requirement_matches"]
        if match["requirement"]["text"] == "Python"
    )
    assert python_match["status"] == "matched"
    assert python_match["supporting_evidence"]
    assert all(item["verified"] is True for item in python_match["supporting_evidence"])
    assert "AWS" in explanation["missing_requirements"]

    reviewed = client.post(
        f"/api/v1/career-analyses/{run['id']}/review",
        headers=headers,
        json={
            "decision": "approve",
            "review_notes": "Reviewed candidate facts and citations.",
            "export_formats": ["docx", "pdf"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = reviewed.json()
    assert approved["status"] == "completed"
    assert approved["resume_draft"]["status"] == "approved"
    assert approved["application_record"]["status"] == "saved"
    assert approved["application_record"]["evidence_coverage_score"] == approved[
        "evidence_coverage_score"
    ]
    assert {item["output_format"] for item in approved["generated_documents"]} == {
        "docx",
        "pdf",
    }
    assert all(
        Path(item["file_path"]).parent == output_directory
        for item in approved["generated_documents"]
    )
    assert all(Path(item["file_path"]).is_file() for item in approved["generated_documents"])
    for document in approved["generated_documents"]:
        downloaded = client.get(
            f"/api/v1/documents/{document['id']}/download",
            headers=headers,
        )
        assert downloaded.status_code == 200
        assert downloaded.content

    direct_match = client.post(
        f"/api/v1/jobs/{run['job_description_id']}/match-explain",
        headers=headers,
        json={"candidate_profile_id": candidate_id},
    )
    assert direct_match.status_code == 200, direct_match.text
    assert direct_match.json()["evidence_coverage"] == explanation["evidence_coverage"]

    status_updated = client.patch(
        f"/api/v1/applications/{approved['application_record_id']}/status",
        headers=headers,
        json={"status": "interviewing"},
    )
    assert status_updated.status_code == 200
    assert status_updated.json()["status"] == "interviewing"


def test_golden_flow_rejects_tampered_unsupported_claim_before_export(
    golden_client: tuple[TestClient, Session, Path],
) -> None:
    client, session, output_directory = golden_client
    headers, candidate_id = _authenticated_candidate(client, email="tamper@example.com")
    started = client.post(
        "/api/v1/career-analyses",
        headers=headers,
        json=_golden_request(candidate_id),
    )
    assert started.status_code == 201, started.text
    run = started.json()
    draft = session.get(ResumeDraft, UUID(run["resume_draft_id"]))
    assert draft is not None
    draft.grounding_manifest = [
        *draft.grounding_manifest,
        {
            "claim_type": "project",
            "text": "Deployed a production Kubernetes platform",
            "evidence_ids": [],
        },
    ]
    session.commit()

    reviewed = client.post(
        f"/api/v1/career-analyses/{run['id']}/review",
        headers=headers,
        json={"decision": "approve", "export_formats": ["pdf"]},
    )
    assert reviewed.status_code == 422
    assert reviewed.json()["error"]["code"] == "grounding_validation_failed"
    assert not list(output_directory.iterdir())


def test_golden_flow_failure_reports_stage_run_and_request_ids(
    golden_client: tuple[TestClient, Session, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, _output_directory = golden_client
    headers, candidate_id = _authenticated_candidate(client, email="failure@example.com")

    def fail_job_import(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated local stage failure")

    monkeypatch.setattr(ManualJobImportService, "import_job_posting", fail_job_import)
    response = client.post(
        "/api/v1/career-analyses",
        headers=headers,
        json=_golden_request(candidate_id),
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "career_analysis_execution_error"
    assert error["details"]["stage"] == "job_import"
    assert error["details"]["request_id"] != "unavailable"
    run = session.get(CareerAnalysisRun, UUID(error["details"]["run_id"]))
    assert run is not None
    assert run.status == CareerAnalysisStatus.FAILED
    assert run.error_details["stage"] == "job_import"


def test_missing_openai_key_uses_deterministic_embedding_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = build_embedding_provider()
    assert isinstance(provider, DeterministicHashEmbeddingProvider)
    assert provider.provider_name == "deterministic_local"


def _authenticated_candidate(
    client: TestClient,
    *,
    email: str = "golden@example.com",
) -> tuple[dict[str, str], str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Golden User"},
    )
    assert registered.status_code == 201, registered.text
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/candidates",
        headers=headers,
        json={
            "full_name": "Ada Candidate",
            "email": "ada@example.com",
            "location": "Remote",
            "headline": "Junior Applied AI Engineer",
            "summary": "Python engineer building evidence-grounded FastAPI applications.",
            "skills": [
                {
                    "name": "Python",
                    "category": "Programming Languages",
                    "self_rating": 4,
                    "years_of_experience": 2,
                },
                {
                    "name": "FastAPI",
                    "category": "Backend Development",
                    "self_rating": 4,
                    "years_of_experience": 1,
                },
            ],
            "projects": [
                {
                    "title": "CareerOS",
                    "description": (
                        "Implemented FastAPI endpoints, deterministic matching, and PostgreSQL "
                        "application tracking."
                    ),
                    "technologies": ["Python", "FastAPI", "PostgreSQL"],
                    "outcomes": ["Added automated API and document-generation tests."],
                    "github_url": "https://github.com/example/careeros",
                }
            ],
            "work_experiences": [],
            "education": [
                {
                    "institution": "Example University",
                    "degree": "BS Computer Science",
                    "field_of_study": "Computer Science",
                }
            ],
            "certifications": [],
        },
    )
    assert created.status_code == 201, created.text
    return headers, created.json()["id"]


def _golden_request(candidate_id: str) -> dict[str, object]:
    return {
        "candidate_profile_id": candidate_id,
        "raw_title": "Applied AI Engineer",
        "company_name": "Evidence Labs",
        "location": "Remote",
        "source_platform": "company_site",
        "description_text": (
            "Responsibilities:\n"
            "Build reliable Python and FastAPI services for evidence-grounded AI workflows.\n"
            "Requirements:\n"
            "Python, FastAPI, PostgreSQL, and AWS deployment experience are required.\n"
            "Preferred skills:\n"
            "Docker experience is nice to have."
        ),
        "mode": "mock",
    }
