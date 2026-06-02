"""Service tests for the URL extraction adapter over the existing pipeline."""

import unittest
from decimal import Decimal
from uuid import uuid4

from app.features.job_url_extraction.extractors import BaseJobUrlExtractor
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
from app.services import JobUrlPipelineService
from tests.support import create_test_engine, create_test_session


class StubExtractor(BaseJobUrlExtractor):
    """Return a deterministic extraction result without launching a browser."""

    def __init__(self, result: JobUrlExtractionResult) -> None:
        """Store the extraction result returned by the stub."""
        self.result = result

    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Return the configured extraction result."""
        return self.result


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

    def tearDown(self) -> None:
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

    @staticmethod
    def _request() -> JobUrlPipelineRequest:
        """Build a URL pipeline request."""
        return JobUrlPipelineRequest(
            candidate_profile_id=uuid4(),
            job_url="https://www.linkedin.com/jobs/view/123",
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
