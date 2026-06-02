"""Thin orchestration for manually pasted job postings."""

from sqlalchemy.orm import Session

from app.models import CandidateProfile
from app.models.enums import ApplicationStatus
from app.schemas import (
    ApplicationRecordCreate,
    JobDescriptionCreate,
    ManualJobImportRequest,
    ManualJobImportResult,
)
from app.services.application_tracker import ApplicationTrackerService
from app.services.exceptions import ProfileNotFoundError
from app.services.job_analysis import JobAnalysisService


class ManualJobImportService:
    """Store, analyze, and optionally track one manually pasted job posting."""

    def __init__(self, session: Session) -> None:
        """Build the importer from existing application services."""
        self.session = session
        self.jobs = JobAnalysisService(session)
        self.applications = ApplicationTrackerService(session)

    def import_job_posting(self, request: ManualJobImportRequest) -> ManualJobImportResult:
        """Import pasted job data without scraping, browser automation, or AI calls."""
        self._require_candidate(request.candidate_profile_id)
        job_description = self.jobs.create_job_description(
            JobDescriptionCreate(
                raw_title=request.raw_title,
                company_name=request.company_name,
                location=request.location,
                source_platform=request.source_platform,
                job_url=request.job_url,
                description_text=request.description_text,
                salary_min=request.salary_min,
                salary_max=request.salary_max,
                currency=request.currency,
                employment_type=request.employment_type,
                workplace_type=request.workplace_type,
            )
        )
        analysis = self.jobs.analyze_job_description(job_description.id)
        application_record = None
        if request.create_application_record:
            application_record = self.applications.create_application_record(
                ApplicationRecordCreate(
                    candidate_profile_id=request.candidate_profile_id,
                    job_description_id=job_description.id,
                    job_analysis_id=analysis.id,
                    company_name=request.company_name,
                    role_title=request.raw_title,
                    company_email=request.company_email,
                    job_url=request.job_url,
                    status=ApplicationStatus.NOT_APPLIED,
                )
            )
        return ManualJobImportResult(
            job_description=job_description,
            analysis=analysis,
            application_record=application_record,
        )

    def _require_candidate(self, candidate_profile_id: object) -> CandidateProfile:
        """Require a candidate context even when tracker-record creation is disabled."""
        candidate = self.session.get(CandidateProfile, candidate_profile_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate
