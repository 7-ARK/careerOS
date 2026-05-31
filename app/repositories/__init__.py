"""Repository interfaces for persistence operations."""

from app.repositories.application_tracking import ApplicationRecordRepository
from app.repositories.document_generation import GeneratedDocumentRepository
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
    "ApplicationRecordRepository",
    "CandidateOwnedRepository",
    "CandidateProfileRepository",
    "CareerGoalRepository",
    "CertificationRepository",
    "EducationRepository",
    "GeneratedDocumentRepository",
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
