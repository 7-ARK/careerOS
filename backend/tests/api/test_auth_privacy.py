"""End-to-end API coverage for authentication and candidate ownership."""

import unittest
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.dependencies import (
    get_application_pipeline_service,
    get_db,
    get_document_generation_service,
    get_job_url_pipeline_service,
)
from app.main import app
from tests.support import create_test_engine, create_test_session

OWNER_SCOPED_ROUTE_INVENTORY = (
    (
        "backend/app/api/routes/candidates.py",
        "GET /api/v1/candidates/{candidate_id}",
        "candidate detail",
    ),
    (
        "backend/app/api/routes/candidates.py",
        "PATCH /api/v1/candidates/{candidate_id}",
        "candidate update",
    ),
    (
        "backend/app/api/routes/candidates.py",
        "DELETE /api/v1/candidates/{candidate_id}",
        "candidate delete",
    ),
    (
        "backend/app/api/routes/applications.py",
        "GET /api/v1/applications/{candidate_profile_id}",
        "application list",
    ),
    (
        "backend/app/api/routes/applications.py",
        "PATCH /api/v1/applications/{application_id}/applied",
        "application mark applied",
    ),
    (
        "backend/app/api/routes/applications.py",
        "PATCH /api/v1/applications/{application_id}/not-applied",
        "application mark not applied",
    ),
    (
        "backend/app/api/routes/documents.py",
        "GET /api/v1/documents/{document_id}/download",
        "document download",
    ),
    ("backend/app/api/routes/pipeline.py", "POST /api/v1/pipeline/manual", "manual pipeline"),
    (
        "backend/app/api/routes/job_url_extraction.py",
        "POST /api/v1/pipeline/extract",
        "URL extraction",
    ),
    ("backend/app/api/routes/job_url_extraction.py", "POST /api/v1/pipeline/url", "URL pipeline"),
)


class PipelineShouldNotRun:
    """Fail loudly if privacy checks allow a foreign profile into the pipeline."""

    def run_manual_job_pipeline(self, request: object) -> object:
        raise AssertionError("pipeline must not run for another user's candidate")


class UrlServiceShouldNotRun:
    """Fail loudly if a foreign profile reaches URL extraction."""

    def extract_url(self, request: object) -> object:
        raise AssertionError("URL extraction must not run for another user's candidate")

    def run_url_pipeline(self, request: object) -> object:
        raise AssertionError("URL pipeline must not run for another user's candidate")


class StubDocumentService:
    """Record document resolution before returning foreign document metadata."""

    def __init__(self, candidate_profile_id: str) -> None:
        self.candidate_profile_id = UUID(candidate_profile_id)
        self.requested_document_ids: list[object] = []

    def get_generated_document(self, document_id: object) -> object:
        self.requested_document_ids.append(document_id)
        return SimpleNamespace(
            candidate_profile_id=self.candidate_profile_id,
            file_path=str(Path("missing-private-document.pdf")),
            file_name="private-resume.pdf",
        )


class AuthPrivacyTests(unittest.TestCase):
    """Verify MVP auth behavior and private candidate profiles."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)

        def override_db() -> Iterator[Session]:
            yield self.session

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_register_duplicate_login_and_me(self) -> None:
        registered = self._register("owner@example.com", "Owner")
        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "OWNER@example.com",
                "password": "password123",
                "full_name": "Duplicate",
            },
        )
        wrong_password = self.client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong-password"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "password123"},
        )
        missing_token = self.client.get("/api/v1/auth/me")
        me = self.client.get("/api/v1/auth/me", headers=self._headers(registered))

        self.assertEqual(registered.status_code, 201)
        self.assertEqual(registered.json()["token_type"], "bearer")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["error"]["code"], "duplicate_user")
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(me.json()["email"], "owner@example.com")

    def test_users_only_access_their_own_candidates(self) -> None:
        owner = self._register("owner@example.com", "Owner")
        stranger = self._register("stranger@example.com", "Stranger")
        owner_profile = self._create_profile(owner, "Owner Profile")
        stranger_profile = self._create_profile(stranger, "Stranger Profile")

        owner_list = self.client.get("/api/v1/candidates", headers=self._headers(owner))
        foreign_get = self.client.get(
            f"/api/v1/candidates/{stranger_profile['id']}",
            headers=self._headers(owner),
        )
        foreign_update = self.client.patch(
            f"/api/v1/candidates/{stranger_profile['id']}",
            json={"headline": "Stolen"},
            headers=self._headers(owner),
        )
        foreign_delete = self.client.delete(
            f"/api/v1/candidates/{stranger_profile['id']}",
            headers=self._headers(owner),
        )

        self.assertEqual([item["id"] for item in owner_list.json()], [owner_profile["id"]])
        self.assertEqual(foreign_get.status_code, 404)
        self.assertEqual(foreign_update.status_code, 404)
        self.assertEqual(foreign_delete.status_code, 404)

    def test_pipeline_rejects_another_users_candidate(self) -> None:
        owner = self._register("owner@example.com", "Owner")
        stranger = self._register("stranger@example.com", "Stranger")
        stranger_profile = self._create_profile(stranger, "Stranger Profile")
        app.dependency_overrides[get_application_pipeline_service] = lambda: PipelineShouldNotRun()

        response = self.client.post(
            "/api/v1/pipeline/manual",
            json={
                "candidate_profile_id": stranger_profile["id"],
                "raw_title": "Backend Engineer",
                "company_name": "Example",
                "description_text": "Build reliable Python APIs.",
                "create_application_record": False,
            },
            headers=self._headers(owner),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_url_extraction_rejects_another_users_candidate(self) -> None:
        owner = self._register("owner@example.com", "Owner")
        stranger = self._register("stranger@example.com", "Stranger")
        stranger_profile = self._create_profile(stranger, "Stranger Profile")
        app.dependency_overrides[get_job_url_pipeline_service] = lambda: UrlServiceShouldNotRun()

        for endpoint in ("/api/v1/pipeline/extract", "/api/v1/pipeline/url"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    json={
                        "candidate_profile_id": stranger_profile["id"],
                        "job_url": "https://jobs.lever.co/example/123",
                    },
                    headers=self._headers(owner),
                )

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_document_download_rejects_another_users_candidate(self) -> None:
        owner = self._register("owner@example.com", "Owner")
        stranger = self._register("stranger@example.com", "Stranger")
        stranger_profile = self._create_profile(stranger, "Stranger Profile")
        app.dependency_overrides[get_document_generation_service] = lambda: StubDocumentService(
            stranger_profile["id"]
        )

        response = self.client.get(
            f"/api/v1/documents/{uuid4()}/download",
            headers=self._headers(owner),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_private_candidate_endpoints_require_authentication(self) -> None:
        response = self.client.get("/api/v1/candidates")

        self.assertEqual(response.status_code, 401)

    def test_owner_scoped_route_matrix_rejects_without_disclosure_or_mutation(self) -> None:
        """Reject every foreign resource substitution without changing owner data."""
        from app.models.application_tracking import ApplicationRecord

        owner = self._register("matrix-owner@example.com", "Private Owner")
        stranger = self._register("matrix-stranger@example.com", "Matrix Stranger")
        owner_profile = self._create_profile(owner, "Private Owner Profile")
        self._create_profile(stranger, "Foreign Profile")
        owner_document = self._create_generated_document(UUID(owner_profile["id"]))
        owner_record = ApplicationRecord(
            candidate_profile_id=UUID(owner_profile["id"]),
            company_name="Private Company",
            role_title="Private Role",
            notes="private application note",
            status="not_applied",
        )
        self.session.add(owner_record)
        self.session.commit()

        before = self._serialized_owner_state(
            owner_profile["id"],
            str(owner_record.id),
            str(owner_document.id),
        )
        owner_headers = self._headers(owner)
        stranger_headers = self._headers(stranger)
        app.dependency_overrides[get_application_pipeline_service] = lambda: PipelineShouldNotRun()
        app.dependency_overrides[get_job_url_pipeline_service] = lambda: UrlServiceShouldNotRun()
        document_service = StubDocumentService(owner_profile["id"])
        app.dependency_overrides[get_document_generation_service] = lambda: document_service

        own_candidates = self.client.get("/api/v1/candidates", headers=owner_headers)
        stranger_candidates = self.client.get("/api/v1/candidates", headers=stranger_headers)
        self.assertEqual(own_candidates.status_code, 200)
        self.assertEqual([item["id"] for item in own_candidates.json()], [owner_profile["id"]])
        self.assertEqual(stranger_candidates.status_code, 200)
        self.assertNotIn(
            owner_profile["id"], [item["id"] for item in stranger_candidates.json()]
        )

        foreign_candidate_id = owner_profile["id"]
        foreign_attempts = [
            (
                "candidate detail",
                lambda: self.client.get(
                    f"/api/v1/candidates/{foreign_candidate_id}", headers=stranger_headers
                ),
            ),
            (
                "candidate update",
                lambda: self.client.patch(
                    f"/api/v1/candidates/{foreign_candidate_id}",
                    json={"headline": "Stolen"},
                    headers=stranger_headers,
                ),
            ),
            (
                "candidate delete",
                lambda: self.client.delete(
                    f"/api/v1/candidates/{foreign_candidate_id}", headers=stranger_headers
                ),
            ),
            (
                "application list",
                lambda: self.client.get(
                    f"/api/v1/applications/{owner_profile['id']}", headers=stranger_headers
                ),
            ),
            (
                "application mark applied",
                lambda: self.client.patch(
                    f"/api/v1/applications/{owner_record.id}/applied", headers=stranger_headers
                ),
            ),
            (
                "application mark not applied",
                lambda: self.client.patch(
                    f"/api/v1/applications/{owner_record.id}/not-applied", headers=stranger_headers
                ),
            ),
            (
                "manual pipeline",
                lambda: self.client.post(
                    "/api/v1/pipeline/manual",
                    json={
                        "candidate_profile_id": owner_profile["id"],
                        "raw_title": "Private Role",
                        "company_name": "Private Company",
                        "description_text": "Private description.",
                        "create_application_record": False,
                    },
                    headers=stranger_headers,
                ),
            ),
            (
                "URL extraction",
                lambda: self.client.post(
                    "/api/v1/pipeline/extract",
                    json={
                        "candidate_profile_id": owner_profile["id"],
                        "job_url": "https://jobs.example.com/private",
                    },
                    headers=stranger_headers,
                ),
            ),
            (
                "URL pipeline",
                lambda: self.client.post(
                    "/api/v1/pipeline/url",
                    json={
                        "candidate_profile_id": owner_profile["id"],
                        "job_url": "https://jobs.example.com/private",
                    },
                    headers=stranger_headers,
                ),
            ),
            (
                "document download",
                lambda: self.client.get(
                    f"/api/v1/documents/{owner_document.id}/download", headers=stranger_headers
                ),
            ),
        ]
        self.assertEqual(
            sorted(operation for operation, _ in foreign_attempts),
            sorted(operation for _, _, operation in OWNER_SCOPED_ROUTE_INVENTORY),
        )

        from inspect import signature

        from app.api.routes import (
            applications,
            candidates,
            documents,
            job_url_extraction,
            pipeline,
        )

        router_inventory = []
        for source_path, router in (
            ("backend/app/api/routes/candidates.py", candidates.router),
            ("backend/app/api/routes/applications.py", applications.router),
            ("backend/app/api/routes/documents.py", documents.router),
            ("backend/app/api/routes/pipeline.py", pipeline.router),
            ("backend/app/api/routes/job_url_extraction.py", job_url_extraction.router),
        ):
            for route in router.routes:
                parameters = signature(route.endpoint).parameters
                owns_path_identifier = {
                    "candidate_id",
                    "candidate_profile_id",
                    "application_id",
                    "document_id",
                }.intersection(parameters)
                request_carries_candidate_identifier = (
                    "request" in parameters
                    and source_path
                    in {
                        "backend/app/api/routes/pipeline.py",
                        "backend/app/api/routes/job_url_extraction.py",
                    }
                )
                if "current_user" in parameters and (
                    owns_path_identifier or request_carries_candidate_identifier
                ):
                    for method in sorted(route.methods):
                        router_inventory.append((source_path, f"{method} {route.path}"))
        self.assertEqual(
            [(source_path, operation) for source_path, operation, _ in OWNER_SCOPED_ROUTE_INVENTORY],
            router_inventory,
        )

        expected_not_found_payload = {
            "error": {"code": "not_found", "message": "Resource was not found."}
        }
        private_values = (
            owner_profile["id"],
            owner_profile["email"],
            owner_profile["full_name"],
            str(owner_record.id),
            str(owner_document.id),
            owner_record.company_name,
            owner_record.role_title,
            owner_record.notes,
            owner_document.file_name,
            owner_document.file_path,
        )
        for operation, attempt in foreign_attempts:
            with self.subTest(operation=operation):
                response = attempt()
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), expected_not_found_payload)
                for private_value in private_values:
                    if private_value is not None:
                        self.assertNotIn(private_value, response.text)

        self.assertEqual(document_service.requested_document_ids, [owner_document.id])
        self.session.expire_all()
        after = self._serialized_owner_state(
            owner_profile["id"],
            str(owner_record.id),
            str(owner_document.id),
        )
        self.assertEqual(after, before)

    def _create_generated_document(self, candidate_profile_id: UUID) -> object:
        """Persist an owner-owned document and its required provenance records."""
        from app.models.document_generation import GeneratedDocument
        from app.models.job_analysis import JobAnalysis, JobDescription
        from app.models.resume_intelligence import ResumeAnalysis, ResumeDraft

        description = JobDescription(raw_title="Private Role", description_text="Private job.")
        self.session.add(description)
        self.session.flush()
        analysis = JobAnalysis(
            job_description_id=description.id,
            revision=1,
            analyzer_name="test",
            analyzer_version="1",
            normalized_title="Private Role",
            seniority_level="mid",
            required_skills=[],
            preferred_skills=[],
            required_technologies=[],
            preferred_technologies=[],
            responsibilities=[],
            qualifications=[],
            soft_skills=[],
            domain_keywords=[],
            ats_keywords=[],
            red_flags=[],
            missing_information=[],
            job_summary="Private job.",
            match_relevant_signals={},
        )
        self.session.add(analysis)
        self.session.flush()
        resume_analysis = ResumeAnalysis(
            candidate_profile_id=candidate_profile_id,
            job_analysis_id=analysis.id,
            overall_match_score=0,
            keyword_match_score=0,
            skills_match_score=0,
            technology_match_score=0,
            experience_match_score=0,
            project_match_score=0,
            education_match_score=0,
            matched_keywords=[],
            missing_keywords=[],
            matched_skills=[],
            missing_skills=[],
            matched_technologies=[],
            missing_technologies=[],
            relevant_projects=[],
            relevant_experiences=[],
            relevant_education=[],
            strengths=[],
            weaknesses=[],
            gap_analysis={},
            tailoring_recommendations=[],
            truthfulness_warnings=[],
            suggested_resume_summary="Private summary.",
            suggested_resume_sections=[],
        )
        self.session.add(resume_analysis)
        self.session.flush()
        draft = ResumeDraft(
            resume_analysis_id=resume_analysis.id,
            candidate_profile_id=candidate_profile_id,
            job_analysis_id=analysis.id,
            title="Private Resume",
            target_role="Private Role",
            summary="Private summary.",
            skills_section=[],
            experience_section=[],
            projects_section=[],
            education_section=[],
            certifications_section=[],
            ats_keywords_used=[],
            omitted_keywords=[],
            truthfulness_notes=[],
        )
        self.session.add(draft)
        self.session.flush()
        document = GeneratedDocument(
            resume_draft_id=draft.id,
            candidate_profile_id=candidate_profile_id,
            job_analysis_id=analysis.id,
            template_name="clean_ats",
            output_format="pdf",
            file_name="private-resume.pdf",
            file_path="missing-private-document.pdf",
        )
        self.session.add(document)
        self.session.commit()
        return document

    def _serialized_owner_state(
        self,
        candidate_id: str,
        application_id: str,
        document_id: str,
    ) -> bytes:
        """Serialize every owner-linked fixture record deterministically."""
        import json

        from sqlalchemy import inspect

        from app.models.application_tracking import ApplicationRecord
        from app.models.document_generation import GeneratedDocument
        from app.models.knowledge_base import CandidateProfile
        from app.models.resume_intelligence import ResumeAnalysis, ResumeDraft

        profile = self.session.get(CandidateProfile, UUID(candidate_id))
        record = self.session.get(ApplicationRecord, UUID(application_id))
        document = self.session.get(GeneratedDocument, UUID(document_id))
        self.assertIsNotNone(profile)
        self.assertIsNotNone(record)
        self.assertIsNotNone(document)
        draft = self.session.get(ResumeDraft, document.resume_draft_id)
        self.assertIsNotNone(draft)
        analysis = self.session.get(ResumeAnalysis, draft.resume_analysis_id)
        self.assertIsNotNone(analysis)

        def serialize(record: object) -> dict[str, object]:
            return {
                column.key: getattr(record, column.key)
                for column in inspect(record).mapper.column_attrs
            }

        state = {
            "profile": serialize(profile),
            "application_record": serialize(record),
            "resume_analysis": serialize(analysis),
            "resume_draft": serialize(draft),
            "generated_document": serialize(document),
        }
        return json.dumps(
            state,
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    def _register(self, email: str, full_name: str) -> object:
        return self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "full_name": full_name},
        )

    def _create_profile(self, auth_response: object, full_name: str) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/candidates",
            json={
                "full_name": full_name,
                "education": [],
                "work_experiences": [],
                "projects": [],
                "skills": [],
                "certifications": [],
            },
            headers=self._headers(auth_response),
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    @staticmethod
    def _headers(auth_response: object) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_response.json()['access_token']}"}


if __name__ == "__main__":
    unittest.main()
