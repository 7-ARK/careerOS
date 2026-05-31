"""Provider contract for job-description analyzers."""

from abc import ABC, abstractmethod

from app.schemas import JobAnalysisResult, JobDescriptionInput


class BaseJobAnalyzer(ABC):
    """Convert a captured job description into provider-independent intelligence."""

    @property
    @abstractmethod
    def analyzer_name(self) -> str:
        """Return the stable provider identifier."""

    @property
    @abstractmethod
    def analyzer_version(self) -> str:
        """Return the provider implementation version."""

    @abstractmethod
    def analyze(self, job_description: JobDescriptionInput) -> JobAnalysisResult:
        """Analyze a source posting without persisting it."""
