"""TestClient coverage for careerOS FastAPI v1 endpoints."""

import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from starlette.testclient import TestClient

from app.api.dependencies import (
    get_application_pipeline_service,
    get_application_tracker_service,
    get_current_user,
    get_document_generation_service,
    get_job_url_pipeline_service,
    get_knowledge_base_service,
)
from app.main import app
from app.models.enums import (
    ApplicationStatus,
    DocumentFormat,
    PipelineStage,
    PipelineStatus,
    ResumeTemplateName,
    SourcePlatform,
)
from app.schemas import (
    ApplicationRecordRead,
    CandidateProfileDetailsCreate,
    CandidateProfileDetailsUpdate,
    CandidateProfileRead,
    CandidateProfileSummaryRead,
    JobUrlExtractionResult,
    JobUrlPipelineResult,
    ManualJobPipelineResult,
)
from app.services import GeneratedDocumentNotFoundError, PipelineExecutionError


class StubManualPipelineService:
    """Return or raise a configured manual-pipeline result."""

    def __init__(self, result: object) -> None:
        """Store the configured service response."""
        self.result = result

    def run_manual_job_pipeline(self, request: object) -> ManualJobPipelineResult:
        """Return the configured result or raise it when it is an exception."""
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubUrlPipelineService:
    """Return a configured URL-pipeline result."""

    def __init__(self, result: JobUrlPipelineResult | JobUrlExtractionResult) -> None:
        """Store the configured URL-pipeline response."""
        self.result = result

    def run_url_pipeline(self, request: object) -> JobUrlPipelineResult:
        """Return the configured result."""
        assert isinstance(self.result, JobUrlPipelineResult)
        return self.result

    def extract_url(self, request: object) -> JobUrlExtractionResult:
        """Return the configured extraction result."""
        if isinstance(self.result, JobUrlPipelineResult):
            return self.result.extraction
        return self.result


class StubDocumentService:
    """Return configured generated-document metadata or raise a missing error."""

    def __init__(self, document: object) -> None:
        """Store document metadata or an exception."""
        self.document = document

    def get_generated_document(self, document_id: UUID) -> object:
        """Return metadata or raise the configured exception."""
        if isinstance(self.document, Exception):
            raise self.document
        return self.document


class StubApplicationTrackerService:
    """Return configured lightweight application records."""

    def __init__(self, record: ApplicationRecordRead) -> None:
        """Store one representative tracker record."""
        self.record = record

    def list_candidate_applications(self, candidate_id: UUID) -> list[ApplicationRecordRead]:
        """List the representative record."""
        return [self.record]

    def get_application_record(self, application_id: UUID) -> ApplicationRecordRead:
        """Return the representative record for ownership checks."""
        return self.record

    def mark_as_applied(self, application_id: UUID) -> ApplicationRecordRead:
        """Return an applied copy."""
        return self.record.model_copy(
            update={"status": ApplicationStatus.APPLIED, "applied_at": datetime.now(UTC)}
        )

    def mark_as_not_applied(self, application_id: UUID) -> ApplicationRecordRead:
        """Return a not-applied copy."""
        return self.record.model_copy(
            update={"status": ApplicationStatus.NOT_APPLIED, "applied_at": None}
        )


class StubKnowledgeBaseService:
    """Return configured candidate selection and profile responses."""

    def __init__(self, profile: CandidateProfileRead) -> None:
        """Store one representative candidate profile."""
        self.profile = profile

    def list_profiles(self, user_id: UUID) -> list[CandidateProfileSummaryRead]:
        """Return the candidate identity used by the selector."""
        return [
            CandidateProfileSummaryRead(
                id=self.profile.id,
                full_name=self.profile.full_name,
                email=self.profile.email,
                headline=self.profile.headline,
            )
        ]

    def get_profile(
        self,
        profile_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> CandidateProfileRead:
        """Return the complete candidate profile."""
        return self.profile

    def create_profile_with_details(
        self,
        data: CandidateProfileDetailsCreate,
        *,
        user_id: UUID,
    ) -> CandidateProfileRead:
        """Return a profile populated with the submitted basic fields."""
        return self.profile.model_copy(
            update={
                "full_name": data.full_name,
                "email": data.email,
                "github_url": data.github_url,
            }
        )

    def update_profile_with_details(
        self,
        profile_id: UUID,
        data: CandidateProfileDetailsUpdate,
        *,
        user_id: UUID,
    ) -> CandidateProfileRead:
        """Return a profile populated with submitted update fields."""
        return self.profile.model_copy(update=data.model_dump(exclude_unset=True))

    def delete_profile(self, profile_id: UUID, *, user_id: UUID) -> None:
        """Record a successful no-content deletion."""
        return None


class FastApiEndpointTests(unittest.TestCase):
    """Verify thin HTTP adapters and stable response behavior."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.user = SimpleNamespace(
            id=uuid4(),
            email="user@example.com",
            full_name="Test User",
        )
        self.profile = _candidate_profile(user_id=self.user.id)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_knowledge_base_service] = lambda: StubKnowledgeBaseService(
            self.profile
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "careerOS", "version": "0.1.0"},
        )

    def test_cors_preflight_allows_local_frontend(self) -> None:
        response = self.client.options(
            "/api/v1/pipeline/url",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")

    def test_manual_pipeline_endpoint(self) -> None:
        result = _pipeline_result()
        app.dependency_overrides[get_application_pipeline_service] = lambda: (
            StubManualPipelineService(result)
        )

        response = self.client.post("/api/v1/pipeline/manual", json=_manual_pipeline_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["generated_document_id"], str(result.generated_document_id)
        )
        self.assertEqual(response.json()["match_score"], "75")

    def test_url_pipeline_endpoint(self) -> None:
        result = JobUrlPipelineResult(
            extraction=JobUrlExtractionResult(
                job_url="https://careers.example.com/jobs/backend",
                detected_platform=SourcePlatform.UNKNOWN,
                raw_title="Backend Engineer",
                company_name="Platform Labs",
                description_text="Build reliable Python APIs." * 4,
                extraction_confidence=Decimal("0.8"),
                pipeline_ready=True,
            ),
            pipeline=_pipeline_result(),
        )
        app.dependency_overrides[get_job_url_pipeline_service] = lambda: StubUrlPipelineService(
            result
        )

        response = self.client.post(
            "/api/v1/pipeline/url",
            json={
                "candidate_profile_id": str(uuid4()),
                "job_url": "https://careers.example.com/jobs/backend",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["extraction"]["pipeline_ready"])
        self.assertIsNotNone(response.json()["pipeline"])

    def test_job_url_extraction_endpoint_returns_editable_fields(self) -> None:
        result = JobUrlExtractionResult(
            job_url="https://jobs.lever.co/platform-labs/123",
            detected_platform=SourcePlatform.COMPANY_SITE,
            raw_title="Backend Engineer",
            company_name="Platform Labs",
            location="Remote",
            description_text="Build reliable Python APIs." * 4,
            extraction_confidence=Decimal("0.9"),
            pipeline_ready=True,
        )
        app.dependency_overrides[get_job_url_pipeline_service] = lambda: StubUrlPipelineService(
            result
        )

        response = self.client.post(
            "/api/v1/pipeline/extract",
            json={
                "candidate_profile_id": str(self.profile.id),
                "job_url": result.job_url,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["raw_title"], "Backend Engineer")
        self.assertEqual(response.json()["company_name"], "Platform Labs")
        self.assertEqual(response.json()["detected_platform"], "company_site")

    def test_job_url_extraction_endpoint_rejects_empty_url(self) -> None:
        response = self.client.post(
            "/api/v1/pipeline/extract",
            json={
                "candidate_profile_id": str(self.profile.id),
                "job_url": "",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_document_download_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "resume.pdf"
            file_path.write_bytes(b"%PDF-test")
            app.dependency_overrides[get_document_generation_service] = lambda: StubDocumentService(
                SimpleNamespace(
                    file_path=str(file_path),
                    file_name="resume.pdf",
                    candidate_profile_id=self.profile.id,
                )
            )

            response = self.client.get(f"/api/v1/documents/{uuid4()}/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-test")
        self.assertIn("resume.pdf", response.headers["content-disposition"])

    def test_document_download_returns_404_for_missing_metadata_and_file(self) -> None:
        app.dependency_overrides[get_document_generation_service] = lambda: StubDocumentService(
            GeneratedDocumentNotFoundError("document was not found")
        )
        missing_metadata = self.client.get(f"/api/v1/documents/{uuid4()}/download")
        self.assertEqual(missing_metadata.status_code, 404)
        self.assertEqual(missing_metadata.json()["error"]["code"], "not_found")

        app.dependency_overrides[get_document_generation_service] = lambda: StubDocumentService(
            SimpleNamespace(
                file_path="missing/resume.pdf",
                file_name="resume.pdf",
                candidate_profile_id=self.profile.id,
            )
        )
        missing_file = self.client.get(f"/api/v1/documents/{uuid4()}/download")
        self.assertEqual(missing_file.status_code, 404)
        self.assertEqual(missing_file.json()["error"]["code"], "http_error")

    def test_application_list_and_status_endpoints(self) -> None:
        record = _application_record()
        app.dependency_overrides[get_application_tracker_service] = lambda: (
            StubApplicationTrackerService(record)
        )

        listed = self.client.get(f"/api/v1/applications/{record.candidate_profile_id}")
        applied = self.client.patch(f"/api/v1/applications/{record.id}/applied")
        not_applied = self.client.patch(f"/api/v1/applications/{record.id}/not-applied")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(applied.json()["status"], ApplicationStatus.APPLIED)
        self.assertEqual(not_applied.json()["status"], ApplicationStatus.NOT_APPLIED)

    def test_candidate_list_and_detail_endpoints(self) -> None:
        profile = self.profile
        app.dependency_overrides[get_knowledge_base_service] = lambda: StubKnowledgeBaseService(
            profile
        )

        listed = self.client.get("/api/v1/candidates")
        detail = self.client.get(f"/api/v1/candidates/{profile.id}")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            listed.json(),
            [
                {
                    "id": str(profile.id),
                    "full_name": "Ahmed Raza",
                    "email": "ahmed@example.com",
                    "headline": "AI Engineer",
                }
            ],
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["full_name"], "Ahmed Raza")
        self.assertEqual(detail.json()["skills"], [])

    def test_candidate_create_update_and_delete_endpoints(self) -> None:
        profile = self.profile
        app.dependency_overrides[get_knowledge_base_service] = lambda: StubKnowledgeBaseService(
            profile
        )
        payload = {
            "full_name": "Backend Resume",
            "email": "candidate@example.com",
            "github_url": "https://github.com/candidate",
            "education": [],
            "work_experiences": [],
            "projects": [],
            "skills": [],
            "certifications": [],
        }

        created = self.client.post("/api/v1/candidates", json=payload)
        updated = self.client.patch(
            f"/api/v1/candidates/{profile.id}",
            json={"headline": "Backend Engineer"},
        )
        deleted = self.client.delete(f"/api/v1/candidates/{profile.id}")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["full_name"], "Backend Resume")
        self.assertEqual(created.json()["github_url"], "https://github.com/candidate")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["headline"], "Backend Engineer")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")

    def test_validation_and_pipeline_errors_use_consistent_envelopes(self) -> None:
        app.dependency_overrides[get_application_pipeline_service] = lambda: (
            StubManualPipelineService(_pipeline_result())
        )
        validation = self.client.post("/api/v1/pipeline/manual", json={})
        self.assertEqual(validation.status_code, 422)
        self.assertEqual(validation.json()["error"]["code"], "validation_error")

        app.dependency_overrides[get_application_pipeline_service] = lambda: (
            StubManualPipelineService(
                PipelineExecutionError(PipelineStage.DOCUMENT_GENERATION, "export failed")
            )
        )
        failure = self.client.post("/api/v1/pipeline/manual", json=_manual_pipeline_payload())
        self.assertEqual(failure.status_code, 500)
        self.assertEqual(failure.json()["error"]["code"], "pipeline_execution_error")
        self.assertEqual(
            failure.json()["error"]["details"]["stage"],
            PipelineStage.DOCUMENT_GENERATION,
        )


def _pipeline_result() -> ManualJobPipelineResult:
    """Build a compact successful pipeline response."""
    return ManualJobPipelineResult(
        job_description_id=uuid4(),
        job_analysis_id=uuid4(),
        resume_analysis_id=uuid4(),
        resume_draft_id=uuid4(),
        generated_document_id=uuid4(),
        generated_file_path="generated/resumes/resume.pdf",
        application_record_id=uuid4(),
        company_name="Platform Labs",
        role_title="Backend Engineer",
        match_score=Decimal("75"),
        document_format=DocumentFormat.PDF,
        template_name=ResumeTemplateName.CLEAN_ATS,
        status=PipelineStatus.COMPLETED,
        warnings=[],
        next_actions=["Review the generated resume document."],
    )


def _manual_pipeline_payload() -> dict[str, str]:
    """Build a valid manual-pipeline request payload."""
    return {
        "candidate_profile_id": str(uuid4()),
        "raw_title": "Backend Engineer",
        "company_name": "Platform Labs",
        "source_platform": "linkedin",
        "description_text": "Build reliable Python APIs.",
    }


def _application_record() -> ApplicationRecordRead:
    """Build a lightweight tracker response."""
    now = datetime.now(UTC)
    return ApplicationRecordRead(
        id=uuid4(),
        candidate_profile_id=uuid4(),
        job_description_id=uuid4(),
        job_analysis_id=uuid4(),
        generated_document_id=uuid4(),
        company_name="Platform Labs",
        role_title="Backend Engineer",
        company_email="careers@platform.example",
        job_url="https://example.com/jobs/backend",
        status=ApplicationStatus.NOT_APPLIED,
        notes=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
    )


def _candidate_profile(*, user_id: UUID | None = None) -> CandidateProfileRead:
    """Build a complete candidate profile response."""
    now = datetime.now(UTC)
    return CandidateProfileRead(
        id=uuid4(),
        user_id=user_id or uuid4(),
        full_name="Ahmed Raza",
        email="ahmed@example.com",
        phone=None,
        headline="AI Engineer",
        summary=None,
        location=None,
        linkedin_url=None,
        github_url=None,
        portfolio_url=None,
        created_at=now,
        updated_at=now,
    )


if __name__ == "__main__":
    unittest.main()
