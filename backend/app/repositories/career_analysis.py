"""Repository operations for inspectable golden career-analysis runs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareerAnalysisRun
from app.repositories.knowledge_base import Repository


class CareerAnalysisRunRepository(Repository[CareerAnalysisRun]):
    """Persist and query user-owned career-analysis runs."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CareerAnalysisRun)

    def get_for_user(self, run_id: UUID, user_id: UUID) -> CareerAnalysisRun | None:
        return self.session.scalar(
            select(CareerAnalysisRun).where(
                CareerAnalysisRun.id == run_id,
                CareerAnalysisRun.user_id == user_id,
            )
        )

    def list_for_candidate(
        self,
        candidate_profile_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[CareerAnalysisRun]:
        return list(
            self.session.scalars(
                select(CareerAnalysisRun)
                .where(
                    CareerAnalysisRun.candidate_profile_id == candidate_profile_id,
                    CareerAnalysisRun.user_id == user_id,
                )
                .order_by(CareerAnalysisRun.created_at.desc())
                .limit(limit)
            )
        )
