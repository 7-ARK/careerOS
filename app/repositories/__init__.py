"""Repository interfaces for persistence operations."""

from app.repositories.knowledge_base import (
    ApplicationHistoryRepository,
    CandidateOwnedRepository,
    CandidateProfileRepository,
    CareerGoalRepository,
    CertificationRepository,
    EducationRepository,
    PreferenceRepository,
    ProjectRepository,
    Repository,
    ResumeVersionRepository,
    SkillRepository,
    WorkExperienceRepository,
)

__all__ = [
    "ApplicationHistoryRepository",
    "CandidateOwnedRepository",
    "CandidateProfileRepository",
    "CareerGoalRepository",
    "CertificationRepository",
    "EducationRepository",
    "PreferenceRepository",
    "ProjectRepository",
    "Repository",
    "ResumeVersionRepository",
    "SkillRepository",
    "WorkExperienceRepository",
]
