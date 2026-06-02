"""DOCX resume exporter using python-docx."""

from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor

from app.features.document_generation.templates import RenderedResume, ResumeEntry
from app.models.enums import DocumentFormat

from .base import DocumentExporter


class DocxExporter(DocumentExporter):
    """Write an editable, single-column ATS-safe DOCX resume."""

    output_format = DocumentFormat.DOCX
    extension = ".docx"

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write a styled DOCX document without tables or decorative columns."""
        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)
        styles = document.styles
        styles["Normal"].font.name = resume.style.body_font
        styles["Normal"].font.size = Pt(10)

        title = document.add_heading(resume.full_name, level=0)
        title.runs[0].font.color.rgb = _rgb(resume.style.accent_hex)
        document.add_paragraph(resume.target_role)
        if resume.contact_items:
            document.add_paragraph(" | ".join(resume.contact_items))
        document.add_heading("Professional Summary", level=1)
        document.add_paragraph(resume.summary)
        for resume_section in resume.sections:
            self._add_section(
                document,
                resume_section.title,
                resume_section.entries,
                inline_items=resume_section.inline_items,
            )
        document.save(output_path)

    @staticmethod
    def _add_section(
        document: Document,
        title: str,
        entries: list[ResumeEntry],
        *,
        inline_items: list[str] | None = None,
    ) -> None:
        """Append one ATS-readable DOCX section."""
        document.add_heading(title, level=1)
        if inline_items:
            document.add_paragraph(", ".join(inline_items))
        for entry in entries:
            paragraph = document.add_paragraph()
            paragraph.add_run(entry.heading).bold = True
            if entry.subheading:
                paragraph.add_run(f" | {entry.subheading}")
            if entry.meta:
                paragraph.add_run(f" | {entry.meta}").italic = True
            if entry.body:
                document.add_paragraph(entry.body)
            for bullet in entry.bullets:
                document.add_paragraph(bullet, style="List Bullet")
            for link in entry.links:
                document.add_paragraph(link)


def _rgb(hex_color: str) -> RGBColor:
    """Convert a six-digit hex color into a python-docx RGB value."""
    value = hex_color.lstrip("#")
    return RGBColor.from_string(value)
