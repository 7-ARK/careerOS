"""PDF resume exporter using ReportLab."""

from pathlib import Path
from urllib.parse import urlparse

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.features.document_generation.templates import RenderedResume, ResumeEntry
from app.models.enums import DocumentFormat

from .base import DocumentExporter

BODY_FONT = "CareerOS-Vera"
BOLD_FONT = "CareerOS-Vera-Bold"


class PdfExporter(DocumentExporter):
    """Write a compact, selectable-text ATS-safe PDF resume."""

    output_format = DocumentFormat.PDF
    extension = ".pdf"

    def export(self, resume: RenderedResume, output_path: Path) -> None:
        """Write a compact PDF with portable embedded fonts and selectable text."""
        _register_fonts()
        styles = self._styles(resume)
        story = [
            Paragraph(_escape(resume.full_name), styles["ResumeTitle"]),
            Paragraph(_escape(resume.target_role), styles["ResumeRole"]),
        ]
        if resume.contact_items:
            story.append(Paragraph(_contact_markup(resume.contact_items), styles["Contact"]))
        story.extend(
            [
                Spacer(1, 2),
                Paragraph("Professional Summary", styles["SectionHeading"]),
                Paragraph(_escape(resume.summary), styles["BodyText"]),
            ]
        )
        for section in resume.sections:
            story.extend(
                [Spacer(1, 1), Paragraph(_escape(section.title), styles["SectionHeading"])]
            )
            if section.inline_items:
                story.extend(
                    Paragraph(_escape(item), styles["BodyText"]) for item in section.inline_items
                )
            for entry in section.entries:
                story.extend(self._entry_story(entry, styles))
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.58 * inch,
            leftMargin=0.58 * inch,
            topMargin=0.32 * inch,
            bottomMargin=0.32 * inch,
            initialFontName=BODY_FONT,
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
                fontName=BOLD_FONT,
                fontSize=16,
                leading=17,
                alignment=TA_CENTER,
            ),
            "ResumeRole": ParagraphStyle(
                "ResumeRole",
                parent=styles["BodyText"],
                fontName=BOLD_FONT,
                fontSize=9,
                leading=10,
                alignment=TA_CENTER,
            ),
            "Contact": ParagraphStyle(
                "Contact",
                parent=styles["BodyText"],
                fontName=BODY_FONT,
                fontSize=7.5,
                leading=8.5,
                alignment=TA_CENTER,
            ),
            "SectionHeading": ParagraphStyle(
                "SectionHeading",
                parent=styles["Heading2"],
                textColor=accent,
                fontName=BOLD_FONT,
                fontSize=9.5,
                leading=10.5,
                spaceBefore=1,
                spaceAfter=0.5,
            ),
            "EntryHeading": ParagraphStyle(
                "EntryHeading",
                parent=styles["BodyText"],
                fontName=BOLD_FONT,
                fontSize=8,
                leading=9,
                spaceBefore=1,
            ),
            "BodyText": ParagraphStyle(
                "ResumeBody",
                parent=styles["BodyText"],
                fontName=BODY_FONT,
                fontSize=7.5,
                leading=8.6,
                spaceAfter=0.2,
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
            for value in entry.bullets
        )
        story.extend(
            Paragraph(
                f'<link href="{_escape_attribute(link)}">{_link_label(link)}</link>',
                styles["BodyText"],
            )
            for link in entry.links
        )
        return story


def _escape(value: str) -> str:
    """Escape XML-sensitive characters before ReportLab paragraph rendering."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attribute(value: str) -> str:
    return _escape(value).replace('"', "&quot;")


def _link_label(url: str) -> str:
    host = urlparse(url).netloc.casefold()
    if "github.com" in host:
        return "GitHub"
    if "linkedin.com" in host:
        return "LinkedIn"
    return "Project link"


def _contact_markup(items: list[str]) -> str:
    """Render candidate-owned URLs as concise labeled hyperlinks."""
    values: list[str] = []
    for item in items:
        parsed = urlparse(item)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            label = _link_label(item)
            if label == "Project link":
                label = "Portfolio"
            values.append(f'<link href="{_escape_attribute(item)}">{label}</link>')
        else:
            values.append(_escape(item))
    return " | ".join(values)


def _register_fonts() -> None:
    """Register ReportLab's bundled Bitstream Vera fonts for deterministic embedding."""
    if BODY_FONT in pdfmetrics.getRegisteredFontNames():
        return
    font_directory = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont(BODY_FONT, font_directory / "Vera.ttf"))
    pdfmetrics.registerFont(TTFont(BOLD_FONT, font_directory / "VeraBd.ttf"))
