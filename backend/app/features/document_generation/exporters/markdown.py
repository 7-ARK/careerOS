"""Markdown resume exporter."""

from pathlib import Path

from app.features.document_generation.renderers import MarkdownRenderer
from app.features.document_generation.templates import RenderedResume
from app.models.enums import DocumentFormat

from .base import DocumentExporter


class MarkdownExporter(DocumentExporter):
    """Write a portable Markdown resume."""

    output_format = DocumentFormat.MARKDOWN
    extension = ".md"

    def __init__(self, renderer: MarkdownRenderer | None = None) -> None:
        """Create a Markdown exporter."""
        self.renderer = renderer or MarkdownRenderer()

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write UTF-8 Markdown content."""
        output_path.write_text(self.renderer.render(resume), encoding="utf-8")
