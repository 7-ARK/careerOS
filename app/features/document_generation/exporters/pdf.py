"""PDF resume exporter using ReportLab."""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.features.document_generation.templates import RenderedResume, ResumeEntry
from app.models.enums import DocumentFormat

from .base import DocumentExporter


class PdfExporter(DocumentExporter):
    """Write a compact, selectable-text ATS-safe PDF resume."""

    output_format = DocumentFormat.PDF
    extension = ".pdf"

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write a single-column PDF using built-in fonts and selectable text."""
        styles = self._styles(resume)
        story = [
            Paragraph(_escape(resume.full_name), styles["ResumeTitle"]),
            Paragraph(_escape(resume.target_role), styles["ResumeRole"]),
        ]
        if resume.contact_items:
            story.append(Paragraph(_escape(" | ".join(resume.contact_items)), styles["Contact"]))
        story.extend(
            [
                Spacer(1, 8),
                Paragraph("Professional Summary", styles["SectionHeading"]),
                Paragraph(_escape(resume.summary), styles["BodyText"]),
            ]
        )
        for section in resume.sections:
            story.extend(
                [Spacer(1, 6), Paragraph(_escape(section.title), styles["SectionHeading"])]
            )
            if section.inline_items:
                story.append(
                    Paragraph(_escape(", ".join(section.inline_items)), styles["BodyText"])
                )
            for entry in section.entries:
                story.extend(self._entry_story(entry, styles))
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.55 * inch,
        )
        document.build(story)

    @staticmethod
    def _styles(resume: RenderedResume) -> dict[str, ParagraphStyle]:
        """Create a compact style sheet from code-template hints."""
        styles = getSampleStyleSheet()
        accent = HexColor(resume.style.accent_hex)
        return {
            "ResumeTitle": ParagraphStyle(
                "ResumeTitle",
                parent=styles["Title"],
                textColor=accent,
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=21,
                alignment=TA_CENTER,
            ),
            "ResumeRole": ParagraphStyle(
                "ResumeRole",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                alignment=TA_CENTER,
            ),
            "Contact": ParagraphStyle(
                "Contact",
                parent=styles["BodyText"],
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
            ),
            "SectionHeading": ParagraphStyle(
                "SectionHeading",
                parent=styles["Heading2"],
                textColor=accent,
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=14,
                spaceBefore=3,
                spaceAfter=2,
            ),
            "EntryHeading": ParagraphStyle(
                "EntryHeading",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=11,
                spaceBefore=3,
            ),
            "BodyText": ParagraphStyle(
                "ResumeBody",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=10.5,
                spaceAfter=1,
            ),
        }

    @staticmethod
    def _entry_story(
        entry: ResumeEntry, styles: dict[str, ParagraphStyle]
    ) -> list[Paragraph | Spacer]:
        """Render one structured entry into PDF flowables."""
        heading = entry.heading
        if entry.subheading:
            heading += f" | {entry.subheading}"
        if entry.meta:
            heading += f" | {entry.meta}"
        story: list[Paragraph | Spacer] = [Paragraph(_escape(heading), styles["EntryHeading"])]
        if entry.body:
            story.append(Paragraph(_escape(entry.body), styles["BodyText"]))
        story.extend(
            Paragraph(f"- {_escape(value)}", styles["BodyText"])
            for value in [*entry.bullets, *entry.links]
        )
        return story


def _escape(value: str) -> str:
    """Escape XML-sensitive characters before ReportLab paragraph rendering."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
