"""Service tests for the URL extraction adapter over the existing pipeline."""

import tempfile
import threading
import unittest
from decimal import Decimal
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from uuid import UUID, uuid4

from app.features.job_url_extraction.extractors import (
    BaseJobUrlExtractor,
    PlaywrightJobExtractor,
)
from app.models import ApplicationRecord, CandidateProfile, JobDescription
from app.models.enums import (
    DocumentFormat,
    PipelineStatus,
    ResumeTemplateName,
    SourcePlatform,
)
from app.schemas import (
    JobUrlExtractionRequest,
    JobUrlExtractionResult,
    JobUrlPipelineRequest,
    ManualJobPipelineResult,
)
from app.schemas.job_url_extraction import JobUrlExtractionOutcome
from app.services import ApplicationPipelineService, JobUrlPipelineService
from tests.support import create_test_engine, create_test_session, create_test_user


class StubExtractor(BaseJobUrlExtractor):
    """Return a deterministic extraction result without launching a browser."""

    def __init__(self, result: JobUrlExtractionResult) -> None:
        """Store the extraction result returned by the stub."""
        self.result = result

    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Return the configured extraction result."""
        return self.result


class QuietFixtureRequestHandler(SimpleHTTPRequestHandler):
    """Serve fixture files without writing HTTP request logs during tests."""

    def log_message(self, format: str, *args: object) -> None:
        """Suppress deterministic fixture-server request logging."""
        return None


class LocalFixtureExtractor(BaseJobUrlExtractor):
    """Parse fixture documents fetched from a deterministic loopback server."""

    def __init__(self) -> None:
        """Reuse the production parser for loopback-served fixture content."""
        self.parser = PlaywrightJobExtractor()

    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Fetch and parse the actual fixture document represented by the URL."""
        with urlopen(request.job_url, timeout=1) as response:  # noqa: S310
            visible_text = response.read().decode("utf-8")
        if request.job_url.endswith("unsupported.html"):
            return self.parser.extract(request)
        return self.parser.extract_from_visible_text(
            job_url=request.job_url,
            page_title="Backend Engineer - Platform Labs",
            visible_text=visible_text,
        )


class StubPipeline:
    """Record requests delegated to the existing manual pipeline boundary."""

    def __init__(self) -> None:
        """Initialize an empty request log."""
        self.requests = []

    def run_manual_job_pipeline(self, request):
        """Record conversion output and return a compact pipeline result."""
        self.requests.append(request)
        return ManualJobPipelineResult(
            job_description_id=uuid4(),
            job_analysis_id=uuid4(),
            resume_analysis_id=uuid4(),
            resume_draft_id=uuid4(),
            generated_document_id=uuid4(),
            generated_file_path="generated/resumes/resume.pdf",
            application_record_id=uuid4(),
            company_name=request.company_name,
            role_title=request.raw_title,
            match_score=Decimal("75"),
            document_format=request.document_format,
            template_name=request.resume_template_name,
            status=PipelineStatus.COMPLETED,
            warnings=[],
            next_actions=[],
        )


class JobUrlPipelineServiceTests(unittest.TestCase):
    """Verify conversion and pipeline-ready gating without a real browser."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        user = create_test_user(self.session)
        self.profile = CandidateProfile(user_id=user.id, full_name="Grace Hopper")
        self.session.add(self.profile)
        self.session.commit()
        self.fixture_directory = tempfile.TemporaryDirectory()
        fixture_path = Path(self.fixture_directory.name)
        (fixture_path / "backend-engineer.html").write_text(
            "Backend Engineer\n"
            "Platform Labs\n"
            "Remote\n"
            "Build reliable Python APIs, FastAPI services, PostgreSQL integrations, "
            "and automation workflows with a collaborative engineering team.",
            encoding="utf-8",
        )
        (fixture_path / "malformed.html").write_text("Unavailable", encoding="utf-8")
        (fixture_path / "unsupported.html").write_text(
            "Unsupported source fixture document.", encoding="utf-8"
        )
        handler = partial(QuietFixtureRequestHandler, directory=self.fixture_directory.name)
        self.fixture_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.fixture_thread = threading.Thread(
            target=self.fixture_server.serve_forever,
            daemon=True,
        )
        self.fixture_thread.start()
        base_url = f"http://127.0.0.1:{self.fixture_server.server_port}"
        self.success_fixture_url = f"{base_url}/backend-engineer.html"
        self.malformed_fixture_url = f"{base_url}/malformed.html"
        self.unsupported_fixture_url = f"{base_url}/unsupported.html"

    def tearDown(self) -> None:
        self.fixture_server.shutdown()
        self.fixture_server.server_close()
        self.fixture_thread.join()
        self.fixture_directory.cleanup()
        self.session.close()
        self.engine.dispose()

    def test_ready_extraction_converts_to_manual_pipeline_request(self) -> None:
        pipeline = StubPipeline()
        extraction = self._extraction(pipeline_ready=True)
        service = JobUrlPipelineService(
            self.session,
            extractor=StubExtractor(extraction),
            pipeline=pipeline,
        )

        result = service.run_url_pipeline(self._request())

        self.assertIsNotNone(result.pipeline)
        self.assertEqual(len(pipeline.requests), 1)
        delegated = pipeline.requests[0]
        self.assertEqual(delegated.raw_title, "Backend Engineer")
        self.assertEqual(delegated.company_name, "Platform Labs")
        self.assertEqual(delegated.source_platform, SourcePlatform.LINKEDIN)
        self.assertEqual(delegated.document_format, DocumentFormat.PDF)
        self.assertEqual(delegated.resume_template_name, ResumeTemplateName.CLEAN_ATS)

    def test_not_ready_extraction_does_not_run_pipeline(self) -> None:
        pipeline = StubPipeline()
        extraction = self._extraction(
            pipeline_ready=False,
            raw_title=None,
            company_name=None,
            description_text="",
            extraction_warnings=["Use manual import fallback."],
        )
        service = JobUrlPipelineService(
            self.session,
            extractor=StubExtractor(extraction),
            pipeline=pipeline,
        )

        result = service.run_url_pipeline(self._request())

        self.assertIsNone(result.pipeline)
        self.assertEqual(pipeline.requests, [])

    def test_loopback_fixture_urls_return_distinct_typed_outcomes(self) -> None:
        pipeline = StubPipeline()
        service = JobUrlPipelineService(
            self.session,
            extractor=LocalFixtureExtractor(),
            pipeline=pipeline,
        )
        cases = (
            (self.success_fixture_url, JobUrlExtractionOutcome.SUCCESS),
            (self.unsupported_fixture_url, JobUrlExtractionOutcome.UNSUPPORTED_SOURCE),
            (self.malformed_fixture_url, JobUrlExtractionOutcome.EXTRACTION_FAILURE),
        )

        for job_url, outcome in cases:
            with self.subTest(job_url=job_url):
                result = service.run_url_pipeline(self._request(job_url=job_url))

                self.assertEqual(result.extraction.outcome, outcome)
                if outcome is JobUrlExtractionOutcome.SUCCESS:
                    self.assertEqual(result.extraction.raw_title, "Backend Engineer")
                    self.assertEqual(result.extraction.company_name, "Platform Labs")
                    self.assertIn("PostgreSQL integrations", result.extraction.description_text)
                    self.assertIsNotNone(result.pipeline)
                else:
                    self.assertIsNone(result.pipeline)

        self.assertEqual(len(pipeline.requests), 1)

    def test_malformed_fixture_does_not_persist_partial_records(self) -> None:
        before = self._persisted_counts()
        service = JobUrlPipelineService(
            self.session,
            extractor=LocalFixtureExtractor(),
            pipeline=ApplicationPipelineService(self.session),
        )

        result = service.run_url_pipeline(
            self._request(
                job_url=self.malformed_fixture_url,
                candidate_profile_id=self.profile.id,
            )
        )

        self.assertEqual(
            result.extraction.outcome,
            JobUrlExtractionOutcome.EXTRACTION_FAILURE,
        )
        self.assertFalse(result.extraction.pipeline_ready)
        self.assertIsNone(result.pipeline)
        self.assertEqual(self._persisted_counts(), before)

    def test_failure_outcomes_do_not_persist_partial_records(self) -> None:
        failures = (
            self._extraction(
                detected_platform=SourcePlatform.UNKNOWN,
                outcome=JobUrlExtractionOutcome.UNSUPPORTED_SOURCE,
                message="This job source is not supported. Paste the job description manually.",
                pipeline_ready=True,
            ),
            self._extraction(
                outcome=JobUrlExtractionOutcome.EXTRACTION_FAILURE,
                message=(
                    "We could not read a complete job posting. "
                    "Paste the job description manually."
                ),
                pipeline_ready=True,
            ),
        )

        for extraction in failures:
            with self.subTest(outcome=extraction.outcome):
                before = self._persisted_counts()
                service = JobUrlPipelineService(
                    self.session,
                    extractor=StubExtractor(extraction),
                    pipeline=ApplicationPipelineService(self.session),
                )

                result = service.run_url_pipeline(
                    self._request(candidate_profile_id=self.profile.id)
                )

                self.assertEqual(result.extraction.outcome, extraction.outcome)
                self.assertTrue(result.extraction.pipeline_ready)
                self.assertIsNone(result.pipeline)
                self.assertEqual(self._persisted_counts(), before)

    def test_extract_url_returns_fields_without_running_pipeline(self) -> None:
        pipeline = StubPipeline()
        extraction = self._extraction(pipeline_ready=True)
        service = JobUrlPipelineService(
            self.session,
            extractor=StubExtractor(extraction),
            pipeline=pipeline,
        )

        result = service.extract_url(JobUrlExtractionRequest(**self._request().model_dump()))

        self.assertEqual(result, extraction)
        self.assertEqual(pipeline.requests, [])

    def _persisted_counts(self) -> tuple[int, int]:
        """Re-query persisted rows instead of relying on an identity-map snapshot."""
        self.session.expire_all()
        return (
            self.session.query(JobDescription).count(),
            self.session.query(ApplicationRecord).count(),
        )

    @staticmethod
    def _request(
        *,
        job_url: str = "https://www.linkedin.com/jobs/view/123",
        candidate_profile_id: UUID | None = None,
    ) -> JobUrlPipelineRequest:
        """Build a URL pipeline request."""
        return JobUrlPipelineRequest(
            candidate_profile_id=candidate_profile_id or uuid4(),
            job_url=job_url,
            company_email="careers@platform.example",
        )

    @staticmethod
    def _extraction(**overrides: object) -> JobUrlExtractionResult:
        """Build one extractor result."""
        values = {
            "job_url": "https://www.linkedin.com/jobs/view/123",
            "detected_platform": SourcePlatform.LINKEDIN,
            "raw_title": "Backend Engineer",
            "company_name": "Platform Labs",
            "location": "Remote",
            "description_text": "Build reliable Python APIs and FastAPI services." * 3,
            "extraction_confidence": Decimal("0.9"),
            "extraction_warnings": [],
            "pipeline_ready": True,
        }
        values.update(overrides)
        return JobUrlExtractionResult(**values)


if __name__ == "__main__":
    unittest.main()
