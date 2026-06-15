"""Transactional orchestration for the lightweight application tracker."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    ApplicationRecord,
    CandidateProfile,
    GeneratedDocument,
    JobAnalysis,
    JobDescription,
)
from app.models.enums import ApplicationStatus
from app.repositories import ApplicationRecordRepository
from app.schemas import ApplicationRecordCreate, ApplicationRecordRead, ApplicationRecordUpdate
from app.services.exceptions import (
    ApplicationRecordNotFoundError,
    InvalidApplicationReferenceError,
    ProfileNotFoundError,
)


class ApplicationTrackerService:
    """Track a candidate's simple applied or not-applied job records."""

    def __init__(self, session: Session) -> None:
        """Build the lightweight tracker service."""
        self.session = session
        self.applications = ApplicationRecordRepository(session)

    def create_application_record(self, data: ApplicationRecordCreate) -> ApplicationRecordRead:
        """Create one lightweight tracker record with validated optional links."""
        self._require_candidate(data.candidate_profile_id)
        self._validate_links(
            candidate_profile_id=data.candidate_profile_id,
            job_description_id=data.job_description_id,
            job_analysis_id=data.job_analysis_id,
            generated_document_id=data.generated_document_id,
        )
        values = data.model_dump()
        values["status"] = str(data.status)
        values["applied_at"] = self._applied_at(data.status, data.applied_at)
        record = self.applications.create(**values)
        self._commit()
        return ApplicationRecordRead.model_validate(record)

    def update_application_record(
        self,
        application_record_id: UUID,
        data: ApplicationRecordUpdate,
    ) -> ApplicationRecordRead:
        """Update editable tracker metadata without introducing pipeline logic."""
        record = self._require_record(application_record_id)
        values = data.model_dump(exclude_unset=True)
        candidate_profile_id = record.candidate_profile_id
        self._validate_links(
            candidate_profile_id=candidate_profile_id,
            job_description_id=values.get("job_description_id", record.job_description_id),
            job_analysis_id=values.get("job_analysis_id", record.job_analysis_id),
            generated_document_id=values.get("generated_document_id", record.generated_document_id),
        )
        if "status" in values:
            values["status"] = str(values["status"])
            values["applied_at"] = self._applied_at(
                ApplicationStatus(values["status"]),
                record.applied_at,
            )
        self.applications.update(record, values)
        self._commit()
        return ApplicationRecordRead.model_validate(record)

    def mark_as_applied(self, application_record_id: UUID) -> ApplicationRecordRead:
        """Mark a record as applied and set its timestamp once."""
        record = self._require_record(application_record_id)
        self.applications.update_status(
            record,
            ApplicationStatus.APPLIED,
            applied_at=record.applied_at or datetime.now(UTC),
        )
        self._commit()
        return ApplicationRecordRead.model_validate(record)

    def mark_as_not_applied(self, application_record_id: UUID) -> ApplicationRecordRead:
        """Return a record to not-applied and clear its timestamp."""
        record = self._require_record(application_record_id)
        self.applications.update_status(
            record,
            ApplicationStatus.NOT_APPLIED,
            applied_at=None,
        )
        self._commit()
        return ApplicationRecordRead.model_validate(record)

    def attach_resume_document(
        self, application_record_id: UUID, generated_document_id: UUID | None
    ) -> ApplicationRecordRead:
        """Attach or clear the locally generated resume selected for a role."""
        record = self._require_record(application_record_id)
        self._validate_links(
            candidate_profile_id=record.candidate_profile_id,
            job_description_id=record.job_description_id,
            job_analysis_id=record.job_analysis_id,
            generated_document_id=generated_document_id,
        )
        self.applications.attach_generated_document(record, generated_document_id)
        self._commit()
        return ApplicationRecordRead.model_validate(record)

    def list_candidate_applications(
        self, candidate_profile_id: UUID
    ) -> list[ApplicationRecordRead]:
        """List tracker records for one candidate."""
        return self._read_many(self.applications.list_by_candidate(candidate_profile_id))

    def get_application_record(self, application_record_id: UUID) -> ApplicationRecordRead:
        """Return one application record for route-level ownership checks."""
        return ApplicationRecordRead.model_validate(self._require_record(application_record_id))

    def list_applied_applications(
        self, candidate_profile_id: UUID | None = None
    ) -> list[ApplicationRecordRead]:
        """List applied tracker records, optionally for one candidate."""
        return self._read_many(
            self.applications.list_applied(candidate_profile_id=candidate_profile_id)
        )

    def list_not_applied_applications(
        self, candidate_profile_id: UUID | None = None
    ) -> list[ApplicationRecordRead]:
        """List not-applied tracker records, optionally for one candidate."""
        return self._read_many(
            self.applications.list_not_applied(candidate_profile_id=candidate_profile_id)
        )

    def search_applications(
        self,
        query: str,
        *,
        candidate_profile_id: UUID | None = None,
    ) -> list[ApplicationRecordRead]:
        """Search tracker records by company or role."""
        return self._read_many(
            self.applications.search_by_company_or_role(
                query,
                candidate_profile_id=candidate_profile_id,
            )
        )

    def _require_record(self, application_record_id: UUID) -> ApplicationRecord:
        """Load one lightweight tracker record."""
        record = self.applications.get_by_id(application_record_id)
        if record is None:
            raise ApplicationRecordNotFoundError(
                f"application record {application_record_id} was not found"
            )
        return record

    def _require_candidate(self, candidate_profile_id: UUID) -> CandidateProfile:
        """Load a candidate profile."""
        candidate = self.session.get(CandidateProfile, candidate_profile_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate

    def _validate_links(
        self,
        *,
        candidate_profile_id: UUID,
        job_description_id: object,
        job_analysis_id: object,
        generated_document_id: object,
    ) -> None:
        """Validate optional links only when they are present."""
        job_description = self._get_optional(JobDescription, job_description_id)
        job_analysis = self._get_optional(JobAnalysis, job_analysis_id)
        document = self._get_optional(GeneratedDocument, generated_document_id)
        if (
            job_description is not None
            and job_analysis is not None
            and job_analysis.job_description_id != job_description.id
        ):
            raise InvalidApplicationReferenceError(
                "job analysis does not belong to the selected job description"
            )
        if document is not None and document.candidate_profile_id != candidate_profile_id:
            raise InvalidApplicationReferenceError(
                "generated document does not belong to the selected candidate"
            )
        if (
            document is not None
            and job_analysis is not None
            and document.job_analysis_id != job_analysis.id
        ):
            raise InvalidApplicationReferenceError(
                "generated document does not belong to the selected job analysis"
            )

    def _get_optional[ModelT](
        self,
        model: type[ModelT],
        entity_id: object,
    ) -> ModelT | None:
        """Load an optional linked entity or reject an unknown UUID."""
        if entity_id is None:
            return None
        entity = self.session.get(model, entity_id)
        if entity is None:
            raise InvalidApplicationReferenceError(f"{model.__name__} {entity_id} was not found")
        return entity

    @staticmethod
    def _applied_at(status: ApplicationStatus, applied_at: datetime | None) -> datetime | None:
        """Keep the applied timestamp aligned with the two-state lifecycle."""
        if status == ApplicationStatus.NOT_APPLIED:
            return None
        return applied_at or datetime.now(UTC)

    @staticmethod
    def _read_many(records: list[ApplicationRecord]) -> list[ApplicationRecordRead]:
        """Serialize a list of tracker records."""
        return [ApplicationRecordRead.model_validate(record) for record in records]

    def _commit(self) -> None:
        """Commit tracker changes and rollback consistently on failure."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
