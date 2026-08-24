"""Persistence models for careerOS domain entities."""

from app.models.application_tracking import ApplicationRecord
from app.models.auth import User
from app.models.career_analysis import CareerAnalysisRun
from app.models.document_generation import GeneratedDocument
from app.models.enums import (
    ApplicationStatus,
    CareerAnalysisStage,
    CareerAnalysisStatus,
    DocumentFormat,
    DocumentGenerationStatus,
    EmploymentType,
    MatchQuality,
    RelocationPreference,
    RemotePreference,
    RequirementMatchStatus,
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
    "CareerAnalysisRun",
    "CareerAnalysisStage",
    "CareerAnalysisStatus",
    "User",
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
    "RequirementMatchStatus",
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
