"""Thin orchestration for Playwright URL extraction and the existing pipeline."""

from sqlalchemy.orm import Session

from app.features.job_url_extraction.extractors import BaseJobUrlExtractor, PlaywrightJobExtractor
from app.schemas import (
    JobUrlExtractionRequest,
    JobUrlExtractionResult,
    JobUrlPipelineRequest,
    JobUrlPipelineResult,
    ManualJobPipelineRequest,
)
from app.services.pipeline import ApplicationPipelineService


class JobUrlPipelineService:
    """Extract one user-authorized URL and optionally run the existing pipeline."""

    def __init__(
        self,
        session: Session,
        *,
        extractor: BaseJobUrlExtractor | None = None,
        pipeline: ApplicationPipelineService | None = None,
    ) -> None:
        """Build an injectable URL adapter over the manual pipeline."""
        self.extractor = extractor or PlaywrightJobExtractor()
        self.pipeline = pipeline or ApplicationPipelineService(session)

    def run_url_pipeline(self, request: JobUrlPipelineRequest) -> JobUrlPipelineResult:
        """Extract visible page data and run the existing pipeline only when ready."""
        extraction = self.extract_url(JobUrlExtractionRequest(**request.model_dump()))
        if not extraction.pipeline_ready:
            return JobUrlPipelineResult(extraction=extraction)
        pipeline_result = self.pipeline.run_manual_job_pipeline(
            self.to_manual_pipeline_request(request, extraction)
        )
        return JobUrlPipelineResult(
            extraction=extraction,
            pipeline=pipeline_result,
        )

    def extract_url(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Extract job fields without starting the downstream resume pipeline."""
        return self.extractor.extract(request)

    @staticmethod
    def to_manual_pipeline_request(
        request: JobUrlPipelineRequest,
        extraction: JobUrlExtractionResult,
    ) -> ManualJobPipelineRequest:
        """Convert ready extracted fields into the established manual pipeline contract."""
        return ManualJobPipelineRequest(
            candidate_profile_id=request.candidate_profile_id,
            raw_title=extraction.raw_title,
            company_name=extraction.company_name,
            location=extraction.location,
            source_platform=extraction.detected_platform,
            job_url=extraction.job_url,
            description_text=extraction.description_text,
            salary_min=extraction.salary_min,
            salary_max=extraction.salary_max,
            currency=extraction.currency,
            employment_type=extraction.employment_type,
            workplace_type=extraction.workplace_type,
            create_application_record=request.create_application_record,
            company_email=request.company_email,
            resume_template_name=request.resume_template_name,
            document_format=request.document_format,
        )
