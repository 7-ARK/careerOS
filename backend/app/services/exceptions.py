"""Business exceptions raised by careerOS services."""


class KnowledgeBaseError(Exception):
    """Base exception for candidate knowledge-base operations."""


class DuplicateUserError(Exception):
    """Raised when registration uses an existing email address."""


class InvalidCredentialsError(Exception):
    """Raised when an account cannot be authenticated."""


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


class DocumentGenerationError(Exception):
    """Base exception for local resume-document generation."""


class GeneratedDocumentNotFoundError(DocumentGenerationError):
    """Raised when generated-document metadata cannot be found."""


class ResumeDraftNotApprovedError(DocumentGenerationError):
    """Raised when document generation targets an unapproved structured draft."""


class UnsupportedDocumentFormatError(DocumentGenerationError):
    """Raised when no exporter is configured for a requested document format."""


class ApplicationTrackerError(Exception):
    """Base exception for lightweight application-tracker operations."""


class ApplicationRecordNotFoundError(ApplicationTrackerError):
    """Raised when a lightweight application record cannot be found."""


class InvalidApplicationReferenceError(ApplicationTrackerError):
    """Raised when linked tracker records do not belong together."""


class CareerAnalysisError(Exception):
    """Base exception for the golden career-analysis flow."""


class CareerAnalysisRunNotFoundError(CareerAnalysisError):
    """Raised when a user-owned career-analysis run cannot be found."""


class InvalidCareerAnalysisStateError(CareerAnalysisError):
    """Raised when a review or export action violates the run lifecycle."""


class CareerAnalysisExecutionError(CareerAnalysisError):
    """Raised when one inspectable Golden Flow stage fails."""

    def __init__(self, stage: object, run_id: object) -> None:
        self.stage = stage
        self.run_id = run_id
        super().__init__(f"career analysis failed during {stage}")


class ResumeGroundingError(CareerAnalysisError):
    """Raised when generated resume claims are not fully evidence-grounded."""


class PipelineError(Exception):
    """Base exception for end-to-end application-pipeline operations."""


class PipelineExecutionError(PipelineError):
    """Raised with the exact stage that failed during pipeline execution."""

    def __init__(self, stage: object, message: str) -> None:
        """Preserve the failed stage and expose a concise error message."""
        self.stage = stage
        super().__init__(f"pipeline failed during {stage}: {message}")
