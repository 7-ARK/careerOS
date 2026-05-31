"""SQLAlchemy repositories for candidate knowledge-base persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, String, cast, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import Base
from app.models import (
    ApplicationHistory,
    ApplicationStatus,
    CandidateProfile,
    CareerGoal,
    Certification,
    Education,
    Preference,
    Project,
    ResumeVersion,
    Skill,
    WorkExperience,
)

ModelT = TypeVar("ModelT", bound=Base)
CandidateOwnedT = TypeVar("CandidateOwnedT", bound=Base)


class Repository(Generic[ModelT]):  # noqa: UP046 - Keep the local Python 3.11 test path usable.
    """Generic SQLAlchemy CRUD repository with filtering and search support."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        """Bind the repository to a session and model."""
        self.session = session
        self.model = model

    def get(self, entity_id: UUID) -> ModelT | None:
        """Return an entity by ID."""
        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        """Stage an entity for persistence and assign database-generated fields."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def create(self, **values: Any) -> ModelT:
        """Create and stage an entity from validated values."""
        return self.add(self.model(**values))

    def update(self, entity: ModelT, values: Mapping[str, Any]) -> ModelT:
        """Apply validated field updates to an entity."""
        for field, value in values.items():
            self._validate_field(field)
            setattr(entity, field, value)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Delete an entity."""
        self.session.delete(entity)
        self.session.flush()

    def list(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelT]:
        """List entities with exact-match filters and pagination."""
        statement = select(self.model)
        statement = self._apply_filters(statement, filters)
        statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def search(
        self,
        query: str,
        *,
        fields: Sequence[str],
        filters: Mapping[str, Any] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelT]:
        """Search configured string-compatible fields with optional filters."""
        if not fields:
            raise ValueError("at least one search field is required")
        expressions = []
        for field in fields:
            self._validate_field(field)
            expressions.append(cast(getattr(self.model, field), String).ilike(f"%{query}%"))
        statement = select(self.model).where(or_(*expressions))
        statement = self._apply_filters(statement, filters)
        statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def _apply_filters(
        self,
        statement: Select[tuple[ModelT]],
        filters: Mapping[str, Any] | None,
    ) -> Select[tuple[ModelT]]:
        """Apply validated exact-match filters."""
        for field, value in (filters or {}).items():
            self._validate_field(field)
            statement = statement.where(getattr(self.model, field) == value)
        return statement

    def _validate_field(self, field: str) -> None:
        """Reject filters and updates for unknown model attributes."""
        if not hasattr(self.model, field):
            raise ValueError(f"{self.model.__name__} has no field '{field}'")


class CandidateOwnedRepository(Repository[CandidateOwnedT]):
    """CRUD repository for records owned by a candidate profile."""

    def list_for_profile(
        self,
        profile_id: UUID,
        *,
        filters: Mapping[str, Any] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[CandidateOwnedT]:
        """List records owned by one candidate profile."""
        return self.list(
            filters={"profile_id": profile_id, **(filters or {})},
            offset=offset,
            limit=limit,
        )

    def search_for_profile(
        self,
        profile_id: UUID,
        query: str,
        *,
        fields: Sequence[str],
        filters: Mapping[str, Any] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[CandidateOwnedT]:
        """Search records owned by one candidate profile."""
        return self.search(
            query,
            fields=fields,
            filters={"profile_id": profile_id, **(filters or {})},
            offset=offset,
            limit=limit,
        )


class CandidateProfileRepository(Repository[CandidateProfile]):
    """Repository for candidate profile aggregate roots."""

    _relationships = (
        CandidateProfile.education,
        CandidateProfile.work_experiences,
        CandidateProfile.projects,
        CandidateProfile.skills,
        CandidateProfile.certifications,
        CandidateProfile.career_goals,
        CandidateProfile.preferences,
        CandidateProfile.resume_versions,
        CandidateProfile.applications,
    )

    def __init__(self, session: Session) -> None:
        """Bind the candidate profile repository."""
        super().__init__(session, CandidateProfile)

    def get_complete(self, profile_id: UUID) -> CandidateProfile | None:
        """Load the complete candidate aggregate efficiently."""
        statement = (
            select(CandidateProfile)
            .where(CandidateProfile.id == profile_id)
            .options(*(selectinload(relationship) for relationship in self._relationships))
        )
        return self.session.scalar(statement)

    def search_profiles(
        self,
        query: str,
        *,
        location: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[CandidateProfile]:
        """Search profiles by identity and summary text."""
        filters = {"location": location} if location else None
        return self.search(
            query,
            fields=("full_name", "email", "headline", "summary"),
            filters=filters,
            offset=offset,
            limit=limit,
        )


class CareerGoalRepository(CandidateOwnedRepository[CareerGoal]):
    """Repository for the one-to-one career-goals record."""

    def __init__(self, session: Session) -> None:
        """Bind the career goal repository."""
        super().__init__(session, CareerGoal)

    def get_for_profile(self, profile_id: UUID) -> CareerGoal | None:
        """Return a candidate's career goals."""
        return self.session.scalar(select(CareerGoal).where(CareerGoal.profile_id == profile_id))


class EducationRepository(CandidateOwnedRepository[Education]):
    """Repository for candidate education records."""

    def __init__(self, session: Session) -> None:
        """Bind the education repository."""
        super().__init__(session, Education)


class WorkExperienceRepository(CandidateOwnedRepository[WorkExperience]):
    """Repository for candidate work experience records."""

    def __init__(self, session: Session) -> None:
        """Bind the work experience repository."""
        super().__init__(session, WorkExperience)


class ProjectRepository(CandidateOwnedRepository[Project]):
    """Repository for candidate project records."""

    def __init__(self, session: Session) -> None:
        """Bind the project repository."""
        super().__init__(session, Project)


class SkillRepository(CandidateOwnedRepository[Skill]):
    """Repository for candidate skills."""

    def __init__(self, session: Session) -> None:
        """Bind the skill repository."""
        super().__init__(session, Skill)


class CertificationRepository(CandidateOwnedRepository[Certification]):
    """Repository for candidate certifications."""

    def __init__(self, session: Session) -> None:
        """Bind the certification repository."""
        super().__init__(session, Certification)


class PreferenceRepository(CandidateOwnedRepository[Preference]):
    """Repository for the one-to-one preferences record."""

    def __init__(self, session: Session) -> None:
        """Bind the preference repository."""
        super().__init__(session, Preference)

    def get_for_profile(self, profile_id: UUID) -> Preference | None:
        """Return a candidate's preferences."""
        return self.session.scalar(select(Preference).where(Preference.profile_id == profile_id))


class ResumeVersionRepository(CandidateOwnedRepository[ResumeVersion]):
    """Repository for derived resume artifacts."""

    def __init__(self, session: Session) -> None:
        """Bind the resume version repository."""
        super().__init__(session, ResumeVersion)


class ApplicationHistoryRepository(CandidateOwnedRepository[ApplicationHistory]):
    """Repository with application-specific search and filtering."""

    def __init__(self, session: Session) -> None:
        """Bind the application history repository."""
        super().__init__(session, ApplicationHistory)

    def filter_for_profile(
        self,
        profile_id: UUID,
        *,
        status: ApplicationStatus | None = None,
        company: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ApplicationHistory]:
        """Filter a candidate's applications by lifecycle state and company."""
        filters: dict[str, Any] = {}
        if status is not None:
            filters["status"] = status
        if company is not None:
            filters["company"] = company
        return self.list_for_profile(profile_id, filters=filters, offset=offset, limit=limit)
