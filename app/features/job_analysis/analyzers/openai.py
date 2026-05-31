"""Future OpenAI analyzer interface without an API dependency."""

from abc import ABC, abstractmethod

from app.features.job_analysis.analyzers.base import BaseJobAnalyzer
from app.schemas import JobAnalysisResult, JobDescriptionInput


class FutureOpenAIJobAnalyzer(BaseJobAnalyzer, ABC):
    """Contract for a future OpenAI structured-output implementation."""

    @property
    def analyzer_name(self) -> str:
        """Return the future provider identifier."""
        return "openai"

    @property
    @abstractmethod
    def analyzer_version(self) -> str:
        """Return the future prompt and structured-output contract version."""

    @abstractmethod
    def analyze(self, job_description: JobDescriptionInput) -> JobAnalysisResult:
        """Analyze a posting with future OpenAI structured outputs."""
