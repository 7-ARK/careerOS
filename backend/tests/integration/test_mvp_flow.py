"""End-to-end API coverage for the supported careerOS MVP workflow."""

import tempfile
import unittest
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.dependencies import (
    get_application_pipeline_service,
    get_db,
    get_document_generation_service,
    get_job_url_pipeline_service,
)
from app.features.document_generation import DocumentGenerationService
from app.features.job_url_extraction.extractors import BaseJobUrlExtractor
from app.features.resume_intelligence.quality import DeterministicResumeQualityEngine
from app.main import app
from app.models.enums import SourcePlatform
from app.schemas import JobUrlExtractionRequest, JobUrlExtractionResult
from app.services import (
    ApplicationPipelineService,
    JobUrlPipelineService,
    ResumeIntelligenceService,
)
from tests.support import create_test_engine, create_test_session


class SuccessfulUrlExtractor(BaseJobUrlExtractor):
    """Return deterministic editable fields without depending on an external job site."""

    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        return JobUrlExtractionResult(
            job_url=request.job_url,
            detected_platform=SourcePlatform.COMPANY_SITE,
            raw_title="Backend Engineer",
            company_name="Platform Labs",
            location="Remote",
            description_text=(
                "Build reliable Python and FastAPI services, PostgreSQL integrations, "
                "automated tests, and production API workflows with an engineering team."
            ),
            extraction_confidence=Decimal("0.9"),
            pipeline_ready=True,
        )


class MvpFlowTests(unittest.TestCase):
    """Verify URL and manual inputs reach real PDF generation and private download."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.output_directory = Path(self.temporary_directory.name)
        self.documents = DocumentGenerationService(
            self.session,
            output_directory=self.output_directory,
        )
        self.pipeline = ApplicationPipelineService(
            self.session,
            resume_intelligence=ResumeIntelligenceService(
                self.session,
                quality_engine=DeterministicResumeQualityEngine(),
            ),
            document_generation=self.documents,
        )
        self.url_service = JobUrlPipelineService(
            self.session,
            extractor=SuccessfulUrlExtractor(),
            pipeline=self.pipeline,
        )

        def override_db() -> Iterator[Session]:
            yield self.session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_application_pipeline_service] = lambda: self.pipeline
        app.dependency_overrides[get_document_generation_service] = lambda: self.documents
        app.dependency_overrides[get_job_url_pipeline_service] = lambda: self.url_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_url_and_manual_flows_generate_downloadable_pdfs(self) -> None:
        registered = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "mvp@example.com",
                "password": "password123",
                "full_name": "MVP User",
            },
        )
        self.assertEqual(registered.status_code, 201)
        logged_in = self.client.post(
            "/api/v1/auth/login",
            json={"email": "mvp@example.com", "password": "password123"},
        )
        self.assertEqual(logged_in.status_code, 200)
        headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}

        created = self.client.post(
            "/api/v1/candidates",
            headers=headers,
            json={
                "full_name": "Ada Candidate",
                "email": "ada@example.com",
                "phone": "+1-555-0100",
                "location": "Remote",
                "linkedin_url": "https://linkedin.com/in/ada",
                "github_url": "https://github.com/ada",
                "portfolio_url": "https://ada.example.com",
                "headline": "Backend Engineer",
                "summary": "Backend engineer building reliable Python services.",
                "skills": [
                    {
                        "name": "Python",
                        "category": "Programming Languages",
                        "self_rating": 4,
                        "years_of_experience": 3,
                    },
                    {
                        "name": "FastAPI",
                        "category": "Backend Development",
                        "self_rating": 4,
                        "years_of_experience": 2,
                    },
                ],
                "projects": [
                    {
                        "title": "Commerce API",
                        "description": "Built a reliable FastAPI commerce service.",
                        "technologies": ["Python", "FastAPI", "PostgreSQL"],
                    }
                ],
                "certifications": [
                    {
                        "name": "Python Development",
                        "issuing_organization": "Example Institute",
                        "issue_date": "2025-01-01",
                    }
                ],
                "work_experiences": [
                    {
                        "job_title": "Junior Backend Engineer",
                        "company": "Example Systems",
                        "start_date": "2023-01-01",
                        "is_current": True,
                        "description": "Built and tested Python API services.",
                    }
                ],
                "education": [
                    {
                        "degree": "BS Computer Science",
                        "institution": "Example University",
                        "end_date": "2023-12-31",
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        candidate_id = created.json()["id"]
        candidates = self.client.get("/api/v1/candidates", headers=headers)
        self.assertEqual([item["id"] for item in candidates.json()], [candidate_id])

        extracted = self.client.post(
            "/api/v1/pipeline/extract",
            headers=headers,
            json={
                "candidate_profile_id": candidate_id,
                "job_url": "https://jobs.lever.co/platform-labs/123",
            },
        )
        self.assertEqual(extracted.status_code, 200)
        self.assertTrue(extracted.json()["pipeline_ready"])
        edited_job = extracted.json() | {"raw_title": "Senior Backend Engineer"}
        url_result = self._run_pipeline(candidate_id, edited_job, headers)
        self.assertEqual(url_result["role_title"], "Senior Backend Engineer")
        self._assert_pdf_download(url_result["generated_document_id"], headers)

        manual_result = self._run_pipeline(
            candidate_id,
            {
                "raw_title": "Python Engineer",
                "company_name": "Manual Company",
                "location": "Remote",
                "description_text": (
                    "Develop Python APIs, automated tests, database integrations, and "
                    "reliable backend services for customer-facing products."
                ),
            },
            headers,
        )
        self.assertEqual(manual_result["company_name"], "Manual Company")
        self._assert_pdf_download(manual_result["generated_document_id"], headers)

    def _run_pipeline(
        self,
        candidate_id: str,
        job: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/pipeline/manual",
            headers=headers,
            json={
                "candidate_profile_id": candidate_id,
                "raw_title": job["raw_title"],
                "company_name": job["company_name"],
                "location": job.get("location"),
                "job_url": job.get("job_url"),
                "description_text": job["description_text"],
                "document_format": "pdf",
                "create_application_record": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document_format"], "pdf")
        return response.json()

    def _assert_pdf_download(self, document_id: str, headers: dict[str, str]) -> None:
        response = self.client.get(
            f"/api/v1/documents/{document_id}/download",
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response.headers["content-type"], "application/pdf")


if __name__ == "__main__":
    unittest.main()
