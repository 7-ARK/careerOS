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
    """Return metadata owned by another candidate for download privacy checks."""

    def __init__(self, candidate_profile_id: str) -> None:
        self.candidate_profile_id = UUID(candidate_profile_id)

    def get_generated_document(self, document_id: object) -> object:
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
