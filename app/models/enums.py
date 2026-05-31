"""Enumerations shared by knowledge-base models and schemas."""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    """Lifecycle states for a job application."""

    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class RemotePreference(StrEnum):
    """Preferred workplace arrangement."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class RelocationPreference(StrEnum):
    """Candidate willingness to relocate."""

    WILLING = "willing"
    NOT_WILLING = "not_willing"
    CONDITIONAL = "conditional"


class ResumeStyle(StrEnum):
    """Supported resume presentation styles."""

    ATS_FOCUSED = "ats_focused"
    CLASSIC = "classic"
    MINIMAL = "minimal"
    MODERN = "modern"
