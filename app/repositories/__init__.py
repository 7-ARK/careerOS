"""Repository interfaces for persistence operations."""

from app.repositories.job_analysis import JobAnalysisRepository, JobDescriptionRepository
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
    "JobAnalysisRepository",
    "JobDescriptionRepository",
    "PreferenceRepository",
    "ProjectRepository",
    "Repository",
    "ResumeVersionRepository",
    "SkillRepository",
    "WorkExperienceRepository",
]
