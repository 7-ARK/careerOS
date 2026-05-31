"""API-ready orchestration for captured postings and structured job analysis."""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.features.job_analysis import BaseJobAnalyzer, RuleBasedJobAnalyzer
from app.models import JobAnalysis, JobDescription
from app.repositories import JobAnalysisRepository, JobDescriptionRepository
from app.schemas import (
    AnalyzedJobRead,
    JobAnalysisCreate,
    JobAnalysisListFilters,
    JobAnalysisRead,
    JobDescriptionAnalysisInput,
    JobDescriptionCreate,
    JobDescriptionRead,
    JobDescriptionUpdate,
)
from app.services.exceptions import JobAnalysisNotFoundError, JobDescriptionNotFoundError


class JobAnalyzerService:
    """Coordinate source capture, provider analysis, persistence, and discovery."""

    def __init__(
        self,
        session: Session,
        analyzer: BaseJobAnalyzer | None = None,
    ) -> None:
        """Build the service with an injectable analyzer provider."""
        self.session = session
        self.analyzer = analyzer or RuleBasedJobAnalyzer()
        self.job_descriptions = JobDescriptionRepository(session)
        self.job_analyses = JobAnalysisRepository(session)

    def create_job_description(self, data: JobDescriptionCreate) -> JobDescriptionRead:
        """Capture a raw job posting for later analysis."""
        job = self.job_descriptions.create(**self._values(data))
        self._commit()
        return JobDescriptionRead.model_validate(job)

    def update_job_description(
        self,
        job_description_id: UUID,
        data: JobDescriptionUpdate,
    ) -> JobDescriptionRead:
        """Update captured posting metadata or source text."""
        job = self._require_job_description(job_description_id)
        incoming = self._values(data, partial=True)
        merged = {
            "raw_job_title": job.raw_job_title,
            "company_name": job.company_name,
            "location": job.location,
            "source_platform": job.source_platform,
            "job_url": job.job_url,
            "description_text": job.description_text,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "employment_type": job.employment_type,
            "workplace_type": job.workplace_type,
            **incoming,
        }
        JobDescriptionCreate.model_validate(merged)
        self.job_descriptions.update(job, incoming)
        self._commit()
        return JobDescriptionRead.model_validate(job)

    def analyze_job_description(self, job_description_id: UUID) -> JobAnalysisRead:
        """Analyze a captured posting and persist a new intelligence revision."""
        job = self._require_job_description(job_description_id)
        payload = self.analyzer.analyze(JobDescriptionAnalysisInput.model_validate(job))
        analysis = self.job_analyses.create(
            **self._values(
                JobAnalysisCreate(
                    job_description_id=job.id,
                    revision=self.job_analyses.next_revision(job.id),
                    analyzer_name=self.analyzer.analyzer_name,
                    analyzer_version=self.analyzer.analyzer_version,
                    **payload.model_dump(),
                )
            )
        )
        self._commit()
        return JobAnalysisRead.model_validate(analysis)

    def get_analysis_by_job_description_id(self, job_description_id: UUID) -> JobAnalysisRead:
        """Return the latest analysis revision for a captured posting."""
        self._require_job_description(job_description_id)
        analysis = self.job_analyses.get_latest_for_job_description(job_description_id)
        if analysis is None:
            raise JobAnalysisNotFoundError(
                f"job description {job_description_id} has not been analyzed"
            )
        return JobAnalysisRead.model_validate(analysis)

    def list_analyzed_jobs(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AnalyzedJobRead]:
        """List captured postings paired with their latest analysis revision."""
        return self._analyzed_job_views(self.job_analyses.list_latest(offset=offset, limit=limit))

    def search_analyzed_jobs(self, filters: JobAnalysisListFilters) -> list[AnalyzedJobRead]:
        """Search analyzed jobs by source metadata and extracted keywords."""
        return self._analyzed_job_views(
            self.job_analyses.search_latest(**filters.model_dump(exclude_none=True))
        )

    def _require_job_description(self, job_description_id: UUID) -> JobDescription:
        """Return a source posting or raise a service-level exception."""
        job = self.job_descriptions.get(job_description_id)
        if job is None:
            raise JobDescriptionNotFoundError(f"job description {job_description_id} was not found")
        return job

    @staticmethod
    def _analyzed_job_views(
        records: list[tuple[JobDescription, JobAnalysis]],
    ) -> list[AnalyzedJobRead]:
        """Serialize source and analysis pairs for API consumers."""
        return [
            AnalyzedJobRead(
                job_description=JobDescriptionRead.model_validate(job),
                analysis=JobAnalysisRead.model_validate(analysis),
            )
            for job, analysis in records
        ]

    @staticmethod
    def _values(data: BaseModel, *, partial: bool = False) -> dict[str, object]:
        """Convert a validated schema into ORM-ready values."""
        return data.model_dump(exclude_unset=partial)

    def _commit(self) -> None:
        """Commit the active transaction and rollback consistently on failure."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
