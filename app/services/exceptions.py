"""Business exceptions raised by careerOS services."""


class KnowledgeBaseError(Exception):
    """Base exception for candidate knowledge-base operations."""


class ProfileNotFoundError(KnowledgeBaseError):
    """Raised when an operation targets a missing candidate profile."""


class DuplicateSkillError(KnowledgeBaseError):
    """Raised when a candidate already has a skill with the same name."""


class InvalidResumeVersionError(KnowledgeBaseError):
    """Raised when an application references another profile's resume version."""


class JobAnalysisError(Exception):
    """Base exception for job analyzer service operations."""


class JobDescriptionNotFoundError(JobAnalysisError):
    """Raised when a job-description source record cannot be found."""


class JobAnalysisNotFoundError(JobAnalysisError):
    """Raised when a captured posting has not been analyzed."""


class ResumeIntelligenceError(Exception):
    """Base exception for resume-intelligence operations."""


class ResumeAnalysisNotFoundError(ResumeIntelligenceError):
    """Raised when a persisted resume analysis cannot be found."""


class ResumeDraftNotFoundError(ResumeIntelligenceError):
    """Raised when a structured resume draft cannot be found."""
