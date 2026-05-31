"""Persistence models for careerOS domain entities."""

from app.models.enums import (
    ApplicationStatus,
    EmploymentType,
    MatchQuality,
    RelocationPreference,
    RemotePreference,
    ResumeDraftStatus,
    ResumeSectionType,
    ResumeStyle,
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
    "ApplicationStatus",
    "CandidateProfile",
    "CareerGoal",
    "Certification",
    "Education",
    "EmploymentType",
    "JobAnalysis",
    "JobDescription",
    "MatchQuality",
    "Preference",
    "Project",
    "RelocationPreference",
    "RemotePreference",
    "ResumeStyle",
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
