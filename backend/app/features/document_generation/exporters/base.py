"""Base contract for local resume exporters."""

from abc import ABC, abstractmethod
from pathlib import Path

from app.features.document_generation.templates import RenderedResume
from app.models.enums import DocumentFormat


class DocumentExporter(ABC):
    """Write one rendered resume into a local document format."""

    output_format: DocumentFormat
    extension: str

    @abstractmethod
    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write the rendered resume to a local file."""
