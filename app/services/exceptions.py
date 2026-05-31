"""Business exceptions raised by careerOS services."""


class KnowledgeBaseError(Exception):
    """Base exception for candidate knowledge-base operations."""


class ProfileNotFoundError(KnowledgeBaseError):
    """Raised when an operation targets a missing candidate profile."""


class DuplicateSkillError(KnowledgeBaseError):
    """Raised when a candidate already has a skill with the same name."""


class InvalidResumeVersionError(KnowledgeBaseError):
    """Raised when an application references another profile's resume version."""
