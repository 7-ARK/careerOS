"""Persistence models for careerOS domain entities."""

from app.models.application_tracking import ApplicationRecord
from app.models.document_generation import GeneratedDocument
from app.models.enums import (
    ApplicationStatus,
    DocumentFormat,
    DocumentGenerationStatus,
    EmploymentType,
    MatchQuality,
    RelocationPreference,
    RemotePreference,
    ResumeDraftStatus,
    ResumeSectionType,
    ResumeStyle,
    ResumeTemplateName,
    SeniorityLevel,
    SourcePlatform,
    WorkplaceType,
)
from app.models.job_analysis import JobAnalysis, JobDescription
from app.models.knowledge_base import (
    ApplicationHistory,
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
from app.models.resume_intelligence import ResumeAnalysis, ResumeDraft

__all__ = [
    "ApplicationHistory",
    "ApplicationRecord",
    "ApplicationStatus",
    "CandidateProfile",
    "CareerGoal",
    "Certification",
    "Education",
    "EmploymentType",
    "DocumentFormat",
    "DocumentGenerationStatus",
    "GeneratedDocument",
    "JobAnalysis",
    "JobDescription",
    "MatchQuality",
    "Preference",
    "Project",
    "RelocationPreference",
    "RemotePreference",
    "ResumeStyle",
    "ResumeTemplateName",
    "ResumeAnalysis",
    "ResumeDraft",
    "ResumeDraftStatus",
    "ResumeSectionType",
    "ResumeVersion",
    "SeniorityLevel",
    "SourcePlatform",
    "Skill",
    "WorkExperience",
    "WorkplaceType",
]
