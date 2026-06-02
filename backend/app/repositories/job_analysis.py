"""Repositories for captured job descriptions and versioned job analyses."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import JobAnalysis, JobDescription
from app.repositories.knowledge_base import Repository


class JobDescriptionRepository(Repository[JobDescription]):
    """Repository for raw job-description source records."""

    def __init__(self, session: Session) -> None:
        """Bind the job-description repository."""
        super().__init__(session, JobDescription)

    def search_sources(
        self,
        query: str,
        *,
        fields: Sequence[str] = (
            "raw_title",
            "company_name",
            "location",
            "source_platform",
            "description_text",
        ),
        offset: int = 0,
        limit: int = 100,
    ) -> list[JobDescription]:
        """Search raw postings by common source fields."""
        return self.search(query, fields=fields, offset=offset, limit=limit)

    def create_job_description(self, **values: Any) -> JobDescription:
        """Create and stage a captured job posting."""
        return self.create(**values)

    def get_job_description(self, job_description_id: UUID) -> JobDescription | None:
        """Return a captured job posting by ID."""
        return self.get(job_description_id)

    def list_job_descriptions(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[JobDescription]:
        """List captured job postings."""
        return self.list(offset=offset, limit=limit)


class JobAnalysisRepository(Repository[JobAnalysis]):
    """Repository for analysis revisions and analyzed-job discovery."""

    def __init__(self, session: Session) -> None:
        """Bind the job-analysis repository."""
        super().__init__(session, JobAnalysis)

    def next_revision(self, job_description_id: UUID) -> int:
        """Return the next analysis revision for a captured posting."""
        statement = select(func.coalesce(func.max(JobAnalysis.revision), 0) + 1).where(
            JobAnalysis.job_description_id == job_description_id
        )
        return self.session.scalar(statement) or 1

    def create_job_analysis(self, **values: Any) -> JobAnalysis:
        """Create and stage a structured analysis revision."""
        return self.create(**values)

    def get_latest_for_job_description(self, job_description_id: UUID) -> JobAnalysis | None:
        """Return the newest analysis revision for a captured posting."""
        statement = (
            select(JobAnalysis)
            .where(JobAnalysis.job_description_id == job_description_id)
            .order_by(JobAnalysis.revision.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_analysis_by_job_description_id(self, job_description_id: UUID) -> JobAnalysis | None:
        """Return the latest analysis revision for a captured posting."""
        return self.get_latest_for_job_description(job_description_id)

    def list_latest(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[JobDescription, JobAnalysis]]:
        """List source postings paired with their latest analysis revision."""
        statement = self._latest_statement().offset(offset).limit(limit)
        return list(self.session.execute(statement).tuples())

    def list_analyzed_jobs(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[JobDescription, JobAnalysis]]:
        """List captured postings paired with their latest analyses."""
        return self.list_latest(offset=offset, limit=limit)

    def search_latest(
        self,
        *,
        keyword: str | None = None,
        title: str | None = None,
        company: str | None = None,
        platform: str | None = None,
        location: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[JobDescription, JobAnalysis]]:
        """Search latest analyzed postings by source and extracted intelligence."""
        statement = self._latest_statement()
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    JobDescription.raw_title.ilike(pattern),
                    JobDescription.company_name.ilike(pattern),
                    JobDescription.location.ilike(pattern),
                    JobDescription.source_platform.ilike(pattern),
                    JobDescription.description_text.ilike(pattern),
                    JobAnalysis.normalized_title.ilike(pattern),
                    cast(JobAnalysis.ats_keywords, String).ilike(pattern),
                    cast(JobAnalysis.domain_keywords, String).ilike(pattern),
                )
            )
        if title:
            pattern = f"%{title}%"
            statement = statement.where(
                or_(
                    JobDescription.raw_title.ilike(pattern),
                    JobAnalysis.normalized_title.ilike(pattern),
                )
            )
        if company:
            statement = statement.where(JobDescription.company_name.ilike(f"%{company}%"))
        if platform:
            statement = statement.where(JobDescription.source_platform.ilike(f"%{platform}%"))
        if location:
            statement = statement.where(JobDescription.location.ilike(f"%{location}%"))
        statement = statement.offset(offset).limit(limit)
        return list(self.session.execute(statement).tuples())

    def search_analyzed_jobs(
        self,
        *,
        keyword: str | None = None,
        title: str | None = None,
        company: str | None = None,
        platform: str | None = None,
        location: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[JobDescription, JobAnalysis]]:
        """Search analyzed jobs by source metadata and extracted keywords."""
        return self.search_latest(
            keyword=keyword,
            title=title,
            company=company,
            platform=platform,
            location=location,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def _latest_statement() -> Any:
        """Build a portable query selecting only the latest analysis revision."""
        revisions = (
            select(
                JobAnalysis.job_description_id,
                func.max(JobAnalysis.revision).label("latest_revision"),
            )
            .group_by(JobAnalysis.job_description_id)
            .subquery()
        )
        return (
            select(JobDescription, JobAnalysis)
            .join(JobAnalysis, JobAnalysis.job_description_id == JobDescription.id)
            .join(
                revisions,
                and_(
                    revisions.c.job_description_id == JobAnalysis.job_description_id,
                    revisions.c.latest_revision == JobAnalysis.revision,
                ),
            )
            .order_by(JobDescription.created_at.desc())
        )
