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


class SourcePlatform(StrEnum):
    """Common job-posting sources while allowing custom stored values."""

    LINKEDIN = "linkedin"
    INDEED = "indeed"
    COMPANY_SITE = "company_site"
    REFERRAL = "referral"
    OTHER = "other"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Common employment arrangements while allowing custom stored values."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    OTHER = "other"
    UNKNOWN = "unknown"


class WorkplaceType(StrEnum):
    """Common workplace arrangements while allowing custom stored values."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    OTHER = "other"
    UNKNOWN = "unknown"


class SeniorityLevel(StrEnum):
    """Normalized seniority levels extracted from job descriptions."""

    INTERN = "intern"
    JUNIOR = "junior"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    PRINCIPAL = "principal"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class ResumeDraftStatus(StrEnum):
    """Lifecycle states for a structured resume draft."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ResumeSectionType(StrEnum):
    """Supported structured resume sections."""

    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"


class MatchQuality(StrEnum):
    """Explainable candidate-job match quality bands."""

    EXCELLENT = "excellent"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    LIMITED = "limited"
