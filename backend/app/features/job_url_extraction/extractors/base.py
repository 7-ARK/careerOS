"""Base contract for user-authorized single-URL job extractors."""

from abc import ABC, abstractmethod

from app.schemas.job_url_extraction import JobUrlExtractionRequest, JobUrlExtractionResult


class BaseJobUrlExtractor(ABC):
    """Extract visible job data from one explicitly provided URL."""

    @abstractmethod
    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Extract visible job-posting fields without submitting any forms."""
