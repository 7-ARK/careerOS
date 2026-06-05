"""Markdown rendering for ATS-safe resume content."""

from app.features.document_generation.templates import RenderedResume, ResumeEntry


class MarkdownRenderer:
    """Render a resume into portable Markdown."""

    def render(self, resume: RenderedResume) -> str:
        """Return a recruiter-readable Markdown resume."""
        lines = [f"# {resume.full_name}", "", f"**{resume.target_role}**"]
        if resume.contact_items:
            lines.extend(("", " | ".join(resume.contact_items)))
        lines.extend(("", "## Professional Summary", "", resume.summary))
        for section in resume.sections:
            lines.extend(("", f"## {section.title}", ""))
            if section.inline_items:
                lines.extend(section.inline_items)
            for entry in section.entries:
                lines.extend(self._entry_lines(entry))
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _entry_lines(entry: ResumeEntry) -> list[str]:
        """Render one section entry."""
        heading = f"### {entry.heading}"
        if entry.subheading:
            heading += f" | {entry.subheading}"
        lines = [heading]
        if entry.meta:
            lines.extend(("", f"*{entry.meta}*"))
        if entry.body:
            lines.extend(("", entry.body))
        lines.extend(f"- {bullet}" for bullet in entry.bullets)
        lines.extend(f"- {link}" for link in entry.links)
        lines.append("")
        return lines
