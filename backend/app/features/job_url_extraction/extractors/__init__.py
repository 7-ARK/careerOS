"""Job URL extraction provider interfaces and implementations."""

from app.features.job_url_extraction.extractors.base import BaseJobUrlExtractor
from app.features.job_url_extraction.extractors.playwright import PlaywrightJobExtractor

__all__ = ["BaseJobUrlExtractor", "PlaywrightJobExtractor"]
