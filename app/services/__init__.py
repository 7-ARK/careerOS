"""Cross-feature application services and orchestration logic."""

from app.services.application_tracker import ApplicationTrackerService
from app.services.exceptions import (
    ApplicationRecordNotFoundError,
    ApplicationTrackerError,
    DocumentGenerationError,
    DuplicateSkillError,
    GeneratedDocumentNotFoundError,
    InvalidApplicationReferenceError,
    InvalidResumeVersionError,
    JobAnalysisError,
    JobAnalysisNotFoundError,
    JobDescriptionNotFoundError,
    KnowledgeBaseError,
    ProfileNotFoundError,
    ResumeAnalysisNotFoundError,
    ResumeDraftNotApprovedError,
    ResumeDraftNotFoundError,
    ResumeIntelligenceError,
    UnsupportedDocumentFormatError,
)
from app.services.job_analysis import JobAnalysisService, JobAnalyzerService
from app.services.job_import import ManualJobImportService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.resume_intelligence import ResumeIntelligenceService

__all__ = [
    "DuplicateSkillError",
    "ApplicationRecordNotFoundError",
    "ApplicationTrackerError",
    "ApplicationTrackerService",
    "DocumentGenerationError",
    "GeneratedDocumentNotFoundError",
    "InvalidResumeVersionError",
    "InvalidApplicationReferenceError",
    "JobAnalysisError",
    "JobAnalysisNotFoundError",
    "JobAnalysisService",
    "JobAnalyzerService",
    "JobDescriptionNotFoundError",
    "KnowledgeBaseError",
    "KnowledgeBaseService",
    "ManualJobImportService",
    "ProfileNotFoundError",
    "ResumeAnalysisNotFoundError",
    "ResumeDraftNotFoundError",
    "ResumeDraftNotApprovedError",
    "ResumeIntelligenceError",
    "ResumeIntelligenceService",
    "UnsupportedDocumentFormatError",
]
