"""Transactional business service for the candidate knowledge base."""

from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import CandidateProfile
from app.repositories import (
    ApplicationHistoryRepository,
    CandidateOwnedRepository,
    CandidateProfileRepository,
    CareerGoalRepository,
    CertificationRepository,
    EducationRepository,
    PreferenceRepository,
    ProjectRepository,
    ResumeVersionRepository,
    SkillRepository,
    WorkExperienceRepository,
)
from app.schemas import (
    ApplicationHistoryCreate,
    ApplicationHistoryRead,
    CandidateProfileCreate,
    CandidateProfileDetailsCreate,
    CandidateProfileDetailsUpdate,
    CandidateProfileRead,
    CandidateProfileSummaryRead,
    CandidateProfileUpdate,
    CareerGoalCreate,
    CareerGoalRead,
    CareerGoalUpdate,
    CertificationCreate,
    CertificationRead,
    EducationCreate,
    EducationRead,
    PreferenceCreate,
    PreferenceRead,
    PreferenceUpdate,
    ProjectCreate,
    ProjectRead,
    ResumeVersionCreate,
    ResumeVersionRead,
    SkillCreate,
    SkillRead,
    WorkExperienceCreate,
    WorkExperienceRead,
)
from app.services.exceptions import (
    DuplicateSkillError,
    InvalidResumeVersionError,
    ProfileNotFoundError,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)
ModelT = TypeVar("ModelT")


class KnowledgeBaseService:
    """Coordinate knowledge-base persistence behind a transaction boundary."""

    def __init__(self, session: Session) -> None:
        """Build a dependency-injection-friendly service from an ORM session."""
        self.session = session
        self.profiles = CandidateProfileRepository(session)
        self.education = EducationRepository(session)
        self.experiences = WorkExperienceRepository(session)
        self.projects = ProjectRepository(session)
        self.skills = SkillRepository(session)
        self.certifications = CertificationRepository(session)
        self.career_goals = CareerGoalRepository(session)
        self.preferences = PreferenceRepository(session)
        self.resume_versions = ResumeVersionRepository(session)
        self.applications = ApplicationHistoryRepository(session)

    def create_candidate_profile(
        self,
        data: CandidateProfileCreate,
        *,
        user_id: UUID,
    ) -> CandidateProfileRead:
        """Create a candidate profile aggregate root."""
        profile = self.profiles.create(user_id=user_id, **self._values(data))
        self._commit()
        return self.get_profile(profile.id, user_id=user_id)

    def create_profile_with_details(
        self,
        data: CandidateProfileDetailsCreate,
        *,
        user_id: UUID,
    ) -> CandidateProfileRead:
        """Create a complete editable candidate profile in one transaction."""
        profile = self.profiles.create(user_id=user_id, **self._profile_values(data))
        self._create_profile_sections(profile.id, data)
        self._commit()
        return self.get_profile(profile.id, user_id=user_id)

    def get_profile(
        self,
        profile_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> CandidateProfileRead:
        """Return the complete candidate knowledge-base aggregate."""
        profile = (
            self.profiles.get_complete_for_user(profile_id, user_id)
            if user_id is not None
            else self.profiles.get_complete(profile_id)
        )
        if profile is None:
            raise ProfileNotFoundError(f"candidate profile {profile_id} was not found")
        return CandidateProfileRead.model_validate(profile)

    def list_profiles(self, user_id: UUID) -> list[CandidateProfileSummaryRead]:
        """Return candidate identities owned by one user."""
        profiles = sorted(
            self.profiles.list_for_user(user_id),
            key=lambda profile: profile.full_name.casefold(),
        )
        return [CandidateProfileSummaryRead.model_validate(profile) for profile in profiles]

    def update_profile(
        self,
        profile_id: UUID,
        data: CandidateProfileUpdate,
        *,
        user_id: UUID | None = None,
    ) -> CandidateProfileRead:
        """Update durable candidate identity fields."""
        profile = self._require_profile(profile_id, user_id=user_id)
        self.profiles.update(profile, self._values(data, partial=True))
        self._commit()
        return self.get_profile(profile_id, user_id=user_id)

    def update_profile_with_details(
        self,
        profile_id: UUID,
        data: CandidateProfileDetailsUpdate,
        *,
        user_id: UUID,
    ) -> CandidateProfileRead:
        """Update basic profile fields and replace each supplied child section."""
        profile = self._require_profile(profile_id, user_id=user_id)
        profile_values = self._profile_values(data, partial=True)
        if profile_values:
            self.profiles.update(profile, profile_values)

        self._replace_section(self.education, profile_id, data.education)
        self._replace_section(self.experiences, profile_id, data.work_experiences)
        self._replace_section(self.projects, profile_id, data.projects)
        self._replace_section(self.skills, profile_id, data.skills)
        self._replace_section(self.certifications, profile_id, data.certifications)
        self._commit()
        return self.get_profile(profile_id, user_id=user_id)

    def delete_profile(self, profile_id: UUID, *, user_id: UUID) -> None:
        """Delete a candidate aggregate and all cascade-owned records."""
        profile = self._require_profile(profile_id, user_id=user_id)
        self.profiles.delete(profile)
        self._commit()

    def add_education(self, profile_id: UUID, data: EducationCreate) -> EducationRead:
        """Add an education record to a candidate profile."""
        entity = self._create_owned(self.education, profile_id, data)
        return EducationRead.model_validate(entity)

    def add_experience(
        self,
        profile_id: UUID,
        data: WorkExperienceCreate,
    ) -> WorkExperienceRead:
        """Add work experience to a candidate profile."""
        entity = self._create_owned(self.experiences, profile_id, data)
        return WorkExperienceRead.model_validate(entity)

    def add_project(self, profile_id: UUID, data: ProjectCreate) -> ProjectRead:
        """Add a project with its evidence and outcomes."""
        entity = self._create_owned(self.projects, profile_id, data)
        return ProjectRead.model_validate(entity)

    def add_skill(self, profile_id: UUID, data: SkillCreate) -> SkillRead:
        """Add a categorized candidate skill."""
        self._require_profile(profile_id)
        duplicate = self.skills.list_for_profile(profile_id, filters={"name": data.name}, limit=1)
        if duplicate:
            raise DuplicateSkillError(f"skill '{data.name}' already exists for this profile")
        skill = self.skills.create(profile_id=profile_id, **self._values(data))
        self._commit()
        return SkillRead.model_validate(skill)

    def add_certification(
        self,
        profile_id: UUID,
        data: CertificationCreate,
    ) -> CertificationRead:
        """Add a professional certification."""
        entity = self._create_owned(self.certifications, profile_id, data)
        return CertificationRead.model_validate(entity)

    def update_career_goals(
        self,
        profile_id: UUID,
        data: CareerGoalCreate | CareerGoalUpdate,
    ) -> CareerGoalRead:
        """Create or update the candidate's career matching constraints."""
        self._require_profile(profile_id)
        existing = self.career_goals.get_for_profile(profile_id)
        incoming = self._values(data, partial=isinstance(data, CareerGoalUpdate))
        if existing is None:
            validated = CareerGoalCreate.model_validate(incoming)
            goals = self.career_goals.create(profile_id=profile_id, **self._values(validated))
        else:
            merged = {
                "target_roles": existing.target_roles,
                "preferred_industries": existing.preferred_industries,
                "salary_min": existing.salary_min,
                "salary_max": existing.salary_max,
                "salary_currency": existing.salary_currency,
                "remote_preference": existing.remote_preference,
                "relocation_preference": existing.relocation_preference,
                "geographic_preferences": existing.geographic_preferences,
                **incoming,
            }
            CareerGoalCreate.model_validate(merged)
            goals = self.career_goals.update(existing, incoming)
        self._commit()
        return CareerGoalRead.model_validate(goals)

    def update_preferences(
        self,
        profile_id: UUID,
        data: PreferenceCreate | PreferenceUpdate,
    ) -> PreferenceRead:
        """Create or update resume, application, and communication preferences."""
        self._require_profile(profile_id)
        existing = self.preferences.get_for_profile(profile_id)
        incoming = self._values(data, partial=isinstance(data, PreferenceUpdate))
        if existing is None:
            validated = PreferenceCreate.model_validate(incoming)
            preferences = self.preferences.create(profile_id=profile_id, **self._values(validated))
        else:
            preferences = self.preferences.update(existing, incoming)
        self._commit()
        return PreferenceRead.model_validate(preferences)

    def create_resume_version(
        self,
        profile_id: UUID,
        data: ResumeVersionCreate,
    ) -> ResumeVersionRead:
        """Record a resume artifact derived from the candidate knowledge base."""
        entity = self._create_owned(self.resume_versions, profile_id, data)
        return ResumeVersionRead.model_validate(entity)

    def record_application(
        self,
        profile_id: UUID,
        data: ApplicationHistoryCreate,
    ) -> ApplicationHistoryRead:
        """Record a job application and optionally the resume version used."""
        self._require_profile(profile_id)
        if data.resume_version_id is not None:
            resume = self.resume_versions.get(data.resume_version_id)
            if resume is None or resume.profile_id != profile_id:
                raise InvalidResumeVersionError(
                    "application resume version must belong to the candidate profile"
                )
        application = self.applications.create(profile_id=profile_id, **self._values(data))
        self._commit()
        return ApplicationHistoryRead.model_validate(application)

    def _require_profile(
        self,
        profile_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> CandidateProfile:
        """Return a candidate profile or raise a domain-specific exception."""
        profile = self.profiles.get(profile_id)
        if profile is None or (user_id is not None and profile.user_id != user_id):
            raise ProfileNotFoundError(f"candidate profile {profile_id} was not found")
        return profile

    def _create_owned(
        self,
        repository: CandidateOwnedRepository[ModelT],
        profile_id: UUID,
        data: SchemaT,
    ) -> ModelT:
        """Create an entity owned by a candidate and commit it."""
        self._require_profile(profile_id)
        entity = repository.create(profile_id=profile_id, **self._values(data))
        self._commit()
        return entity

    def _create_profile_sections(
        self,
        profile_id: UUID,
        data: CandidateProfileDetailsCreate,
    ) -> None:
        """Stage all nested profile sections without committing between records."""
        sections = (
            (self.education, data.education),
            (self.experiences, data.work_experiences),
            (self.projects, data.projects),
            (self.skills, data.skills),
            (self.certifications, data.certifications),
        )
        for repository, records in sections:
            for record in records:
                repository.create(profile_id=profile_id, **self._values(record))

    def _replace_section(
        self,
        repository: CandidateOwnedRepository[ModelT],
        profile_id: UUID,
        records: list[SchemaT] | None,
    ) -> None:
        """Replace one supplied child collection while leaving omitted sections untouched."""
        if records is None:
            return
        for existing in repository.list_for_profile(profile_id):
            repository.delete(existing)
        for record in records:
            repository.create(profile_id=profile_id, **self._values(record))

    @staticmethod
    def _profile_values(data: BaseModel, *, partial: bool = False) -> dict[str, object]:
        """Extract only fields stored directly on the candidate profile table."""
        nested_fields = {
            "education",
            "work_experiences",
            "projects",
            "skills",
            "certifications",
        }
        return data.model_dump(exclude=nested_fields, exclude_unset=partial)

    @staticmethod
    def _values(data: BaseModel, *, partial: bool = False) -> dict[str, object]:
        """Convert a validated command schema to ORM-ready values."""
        return data.model_dump(exclude_unset=partial)

    def _commit(self) -> None:
        """Commit the active transaction and rollback consistently on failure."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
