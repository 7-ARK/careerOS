"""Repository operations for the lightweight application tracker."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ApplicationRecord
from app.models.enums import ApplicationStatus
from app.repositories.knowledge_base import Repository


class ApplicationRecordRepository(Repository[ApplicationRecord]):
    """Persist and query lightweight application records."""

    def __init__(self, session: Session) -> None:
        """Bind the application-record repository."""
        super().__init__(session, ApplicationRecord)

    def get_by_id(self, application_record_id: UUID) -> ApplicationRecord | None:
        """Return one lightweight application record by ID."""
        return self.get(application_record_id)

    def list_by_candidate(
        self, candidate_profile_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[ApplicationRecord]:
        """List records owned by one candidate."""
        return self.list(
            filters={"candidate_profile_id": candidate_profile_id},
            offset=offset,
            limit=limit,
        )

    def list_by_status(
        self,
        status: ApplicationStatus,
        *,
        candidate_profile_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ApplicationRecord]:
        """List records by one of the lightweight tracker states."""
        self._validate_tracker_status(status)
        filters: dict[str, object] = {"status": str(status)}
        if candidate_profile_id is not None:
            filters["candidate_profile_id"] = candidate_profile_id
        return self.list(filters=filters, offset=offset, limit=limit)

    def list_applied(
        self, *, candidate_profile_id: UUID | None = None, offset: int = 0, limit: int = 100
    ) -> list[ApplicationRecord]:
        """List applied records."""
        return self.list_by_status(
            ApplicationStatus.APPLIED,
            candidate_profile_id=candidate_profile_id,
            offset=offset,
            limit=limit,
        )

    def list_not_applied(
        self, *, candidate_profile_id: UUID | None = None, offset: int = 0, limit: int = 100
    ) -> list[ApplicationRecord]:
        """List records that have not been applied to."""
        return self.list_by_status(
            ApplicationStatus.NOT_APPLIED,
            candidate_profile_id=candidate_profile_id,
            offset=offset,
            limit=limit,
        )

    def update_status(
        self,
        record: ApplicationRecord,
        status: ApplicationStatus,
        *,
        applied_at: datetime | None,
    ) -> ApplicationRecord:
        """Update the two-state lifecycle and its application timestamp."""
        self._validate_tracker_status(status)
        return self.update(record, {"status": str(status), "applied_at": applied_at})

    def attach_generated_document(
        self, record: ApplicationRecord, generated_document_id: UUID | None
    ) -> ApplicationRecord:
        """Attach or clear the locally generated resume used for an application."""
        return self.update(record, {"generated_document_id": generated_document_id})

    def search_by_company_or_role(
        self,
        query: str,
        *,
        candidate_profile_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ApplicationRecord]:
        """Search records by company or role title."""
        filters = (
            {"candidate_profile_id": candidate_profile_id}
            if candidate_profile_id is not None
            else None
        )
        return self.search(
            query,
            fields=("company_name", "role_title"),
            filters=filters,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def _validate_tracker_status(status: ApplicationStatus) -> None:
        """Reject legacy pipeline states in the lightweight tracker repository."""
        if status not in {ApplicationStatus.NOT_APPLIED, ApplicationStatus.APPLIED}:
            raise ValueError("lightweight tracker status must be not_applied or applied")
