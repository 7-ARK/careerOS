"""Cross-feature application services and orchestration logic."""

from app.services.application_tracker import ApplicationTrackerService
from app.services.auth import AuthService
from app.services.exceptions import (
    ApplicationRecordNotFoundError,
    ApplicationTrackerError,
    DocumentGenerationError,
    DuplicateSkillError,
    DuplicateUserError,
    GeneratedDocumentNotFoundError,
    InvalidApplicationReferenceError,
    InvalidCredentialsError,
    InvalidResumeVersionError,
    JobAnalysisError,
    JobAnalysisNotFoundError,
    JobDescriptionNotFoundError,
    KnowledgeBaseError,
    PipelineError,
    PipelineExecutionError,
    ProfileNotFoundError,
    ResumeAnalysisNotFoundError,
    ResumeDraftNotApprovedError,
    ResumeDraftNotFoundError,
    ResumeIntelligenceError,
    UnsupportedDocumentFormatError,
)
from app.services.job_analysis import JobAnalysisService, JobAnalyzerService
from app.services.job_import import ManualJobImportService
from app.services.job_url_extraction import JobUrlPipelineService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.pipeline import ApplicationPipelineService
from app.services.resume_intelligence import ResumeIntelligenceService

__all__ = [
    "AuthService",
    "DuplicateSkillError",
    "DuplicateUserError",
    "ApplicationRecordNotFoundError",
    "ApplicationTrackerError",
    "ApplicationTrackerService",
    "ApplicationPipelineService",
    "DocumentGenerationError",
    "GeneratedDocumentNotFoundError",
    "InvalidResumeVersionError",
    "InvalidApplicationReferenceError",
    "InvalidCredentialsError",
    "JobAnalysisError",
    "JobAnalysisNotFoundError",
    "JobAnalysisService",
    "JobAnalyzerService",
    "JobDescriptionNotFoundError",
    "JobUrlPipelineService",
    "KnowledgeBaseError",
    "KnowledgeBaseService",
    "ManualJobImportService",
    "ProfileNotFoundError",
    "PipelineError",
    "PipelineExecutionError",
    "ResumeAnalysisNotFoundError",
    "ResumeDraftNotFoundError",
    "ResumeDraftNotApprovedError",
    "ResumeIntelligenceError",
    "ResumeIntelligenceService",
    "UnsupportedDocumentFormatError",
]
