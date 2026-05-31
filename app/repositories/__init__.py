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
from app.repositories.resume_intelligence import ResumeAnalysisRepository, ResumeDraftRepository

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
    "ResumeAnalysisRepository",
    "ResumeDraftRepository",
    "SkillRepository",
    "WorkExperienceRepository",
]
