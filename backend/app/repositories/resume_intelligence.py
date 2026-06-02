"""Repositories for evidence-backed resume analyses and structured drafts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResumeAnalysis, ResumeDraft
from app.models.enums import ResumeDraftStatus
from app.repositories.knowledge_base import Repository


class ResumeAnalysisRepository(Repository[ResumeAnalysis]):
    """Repository for candidate-job resume analysis snapshots."""

    def __init__(self, session: Session) -> None:
        """Bind the resume-analysis repository."""
        super().__init__(session, ResumeAnalysis)

    def create_resume_analysis(self, **values: object) -> ResumeAnalysis:
        """Create and stage an explainable resume analysis."""
        return self.create(**values)

    def get_latest_by_candidate_job(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> ResumeAnalysis | None:
        """Return the newest analysis for one candidate-job pair."""
        statement = (
            select(ResumeAnalysis)
            .where(
                ResumeAnalysis.candidate_profile_id == candidate_profile_id,
                ResumeAnalysis.job_analysis_id == job_analysis_id,
            )
            .order_by(ResumeAnalysis.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_by_candidate(
        self,
        candidate_profile_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ResumeAnalysis]:
        """List analyses for one candidate."""
        return self.list(
            filters={"candidate_profile_id": candidate_profile_id},
            offset=offset,
            limit=limit,
        )

    def list_by_job(
        self,
        job_analysis_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ResumeAnalysis]:
        """List analyses produced for one structured job analysis."""
        return self.list(
            filters={"job_analysis_id": job_analysis_id},
            offset=offset,
            limit=limit,
        )


class ResumeDraftRepository(Repository[ResumeDraft]):
    """Repository for structured resume drafts."""

    def __init__(self, session: Session) -> None:
        """Bind the resume-draft repository."""
        super().__init__(session, ResumeDraft)

    def create_resume_draft(self, **values: object) -> ResumeDraft:
        """Create and stage a structured resume draft."""
        return self.create(**values)

    def get_latest_by_candidate_job(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> ResumeDraft | None:
        """Return the newest draft for one candidate-job pair."""
        statement = (
            select(ResumeDraft)
            .where(
                ResumeDraft.candidate_profile_id == candidate_profile_id,
                ResumeDraft.job_analysis_id == job_analysis_id,
            )
            .order_by(ResumeDraft.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_by_candidate(
        self,
        candidate_profile_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ResumeDraft]:
        """List drafts for one candidate."""
        return self.list(
            filters={"candidate_profile_id": candidate_profile_id},
            offset=offset,
            limit=limit,
        )

    def list_by_job(
        self,
        job_analysis_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ResumeDraft]:
        """List drafts generated for one structured job analysis."""
        return self.list(filters={"job_analysis_id": job_analysis_id}, offset=offset, limit=limit)

    def update_status(
        self,
        draft: ResumeDraft,
        status: ResumeDraftStatus | str,
    ) -> ResumeDraft:
        """Update a draft lifecycle state."""
        return self.update(draft, {"status": str(status)})
