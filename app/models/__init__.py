"""Persistence models for careerOS domain entities."""

from app.models.enums import (
    ApplicationStatus,
    JobWorkplaceType,
    RelocationPreference,
    RemotePreference,
    ResumeStyle,
    SeniorityLevel,
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

__all__ = [
    "ApplicationHistory",
    "ApplicationStatus",
    "CandidateProfile",
    "CareerGoal",
    "Certification",
    "Education",
    "JobAnalysis",
    "JobDescription",
    "JobWorkplaceType",
    "Preference",
    "Project",
    "RelocationPreference",
    "RemotePreference",
    "ResumeStyle",
    "ResumeVersion",
    "SeniorityLevel",
    "Skill",
    "WorkExperience",
]
