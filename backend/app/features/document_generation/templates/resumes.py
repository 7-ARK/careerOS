"""ATS-safe code-based resume templates."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import CandidateProfile, ResumeDraft
from app.models.enums import ResumeTemplateName

from .base import RenderedResume, ResumeEntry, ResumeSection, ResumeStyle


class ResumeTemplate(ABC):
    """Render structured draft data into an exporter-neutral resume."""

    name: ResumeTemplateName
    style: ResumeStyle

    @abstractmethod
    def render(self, draft: ResumeDraft, candidate: CandidateProfile) -> RenderedResume:
        """Render one approved structured draft."""


class StructuredResumeTemplate(ResumeTemplate):
    """Build ATS-readable sections from structured ResumeDraft fields."""

    section_order: tuple[str, ...]

    def render(self, draft: ResumeDraft, candidate: CandidateProfile) -> RenderedResume:
        """Render only candidate-approved structured facts into ordered sections."""
        available = {
            "skills": self._skills(draft.skills_section),
            "experience": self._experience(draft.experience_section),
            "additional_experience": self._experience(
                draft.experience_section,
                additional=True,
            ),
            "projects": self._projects(draft.projects_section),
            "education": self._education(draft.education_section),
            "certifications": self._certifications(draft.certifications_section),
        }
        sections = [available[name] for name in self.section_order if available[name] is not None]
        return RenderedResume(
            full_name=candidate.full_name,
            target_role=draft.target_role,
            contact_items=self._contact_items(candidate),
            summary=draft.summary,
            sections=sections,
            style=self.style,
        )

    @staticmethod
    def _contact_items(candidate: CandidateProfile) -> list[str]:
        """Return concise candidate-owned contact information."""
        return [
            value
            for value in (
                candidate.email,
                candidate.phone,
                candidate.location,
                candidate.linkedin_url,
                candidate.portfolio_url,
            )
            if value
        ]

    @staticmethod
    def _skills(items: list[dict[str, Any]] | None) -> ResumeSection | None:
        """Render skills without introducing inferred terms."""
        skills = []
        for item in items or []:
            if item.get("skills") and item.get("category"):
                skills.append(f"{item['category']}: {_join_values(item.get('skills'))}")
            elif item.get("name"):
                skills.append(
                    f"{item['name']} ({item['category']})" if item.get("category") else item["name"]
                )
        return ResumeSection(title="Skills", inline_items=skills) if skills else None

    @staticmethod
    def _experience(
        items: list[dict[str, Any]] | None,
        *,
        additional: bool = False,
    ) -> ResumeSection | None:
        """Render selected candidate-owned work experience."""
        entries = [
            ResumeEntry(
                heading=item["job_title"],
                subheading=item.get("company"),
                meta=_date_range(item.get("start_date"), item.get("end_date")),
                body=item.get("description"),
                bullets=_string_list(item.get("achievements")),
            )
            for item in items or []
            if item.get("job_title") and bool(item.get("is_additional")) is additional
        ]
        title = "Additional Experience" if additional else "Experience"
        return ResumeSection(title=title, entries=entries) if entries else None

    @staticmethod
    def _projects(items: list[dict[str, Any]] | None) -> ResumeSection | None:
        """Render selected candidate-owned projects."""
        entries = [
            ResumeEntry(
                heading=item["title"],
                subheading=_join_values(item.get("technologies")),
                body=item.get("description"),
                bullets=_string_list(item.get("outcomes")),
                links=[
                    link for link in (item.get("github_url"), item.get("portfolio_url")) if link
                ],
            )
            for item in items or []
            if item.get("title")
        ]
        return ResumeSection(title="Projects", entries=entries) if entries else None

    @staticmethod
    def _education(items: list[dict[str, Any]] | None) -> ResumeSection | None:
        """Render candidate-owned education."""
        entries = [
            ResumeEntry(
                heading=item["degree"],
                subheading=item.get("institution"),
                body=item.get("field_of_study"),
            )
            for item in items or []
            if item.get("degree")
        ]
        return ResumeSection(title="Education", entries=entries) if entries else None

    @staticmethod
    def _certifications(items: list[dict[str, Any]] | None) -> ResumeSection | None:
        """Render candidate-owned certifications."""
        entries = [
            ResumeEntry(
                heading=item["name"],
                subheading=item.get("issuing_organization"),
                meta=item.get("credential_id"),
                links=[item["credential_url"]] if item.get("credential_url") else [],
            )
            for item in items or []
            if item.get("name")
        ]
        return ResumeSection(title="Certifications", entries=entries) if entries else None


class CleanAtsTemplate(StructuredResumeTemplate):
    """Minimal single-column ATS-first resume template."""

    name = ResumeTemplateName.CLEAN_ATS
    style = ResumeStyle(
        accent_hex="#111111",
        body_font="Arial",
        heading_font="Arial",
        section_divider=False,
        uppercase_sections=True,
    )
    section_order = (
        "skills",
        "projects",
        "experience",
        "education",
        "certifications",
        "additional_experience",
    )


class ModernProfessionalTemplate(StructuredResumeTemplate):
    """Polished single-column resume that remains ATS-safe."""

    name = ResumeTemplateName.MODERN_PROFESSIONAL
    style = ResumeStyle(
        accent_hex="#1F4E5F",
        body_font="Aptos",
        heading_font="Aptos Display",
        section_divider=True,
        uppercase_sections=False,
    )
    section_order = (
        "skills",
        "projects",
        "experience",
        "education",
        "certifications",
        "additional_experience",
    )


TEMPLATES: dict[ResumeTemplateName, ResumeTemplate] = {
    ResumeTemplateName.CLEAN_ATS: CleanAtsTemplate(),
    ResumeTemplateName.MODERN_PROFESSIONAL: ModernProfessionalTemplate(),
}


def get_resume_template(template_name: ResumeTemplateName) -> ResumeTemplate:
    """Return a registered code-based template."""
    return TEMPLATES[template_name]


def _string_list(value: object) -> list[str]:
    """Return non-empty strings from a possibly structured source value."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _join_values(value: object) -> str | None:
    """Join a structured string list for compact display."""
    values = _string_list(value)
    return ", ".join(values) if values else None


def _date_range(start_date: object, end_date: object) -> str | None:
    """Create a readable date range from structured ISO date values."""
    if not start_date and not end_date:
        return None
    values = [str(value) for value in (start_date, end_date or "Present") if value]
    return " - ".join(values) if values else None
