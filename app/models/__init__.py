"""Persistence models for careerOS domain entities."""

from app.models.enums import (
    ApplicationStatus,
    RelocationPreference,
    RemotePreference,
    ResumeStyle,
)
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
    "Preference",
    "Project",
    "RelocationPreference",
    "RemotePreference",
    "ResumeStyle",
    "ResumeVersion",
    "Skill",
    "WorkExperience",
]
