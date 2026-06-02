"""Neutral rendered-resume structures shared by local exporters."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ResumeStyle:
    """Presentation hints interpreted by format-specific exporters."""

    accent_hex: str
    body_font: str
    heading_font: str
    section_divider: bool
    uppercase_sections: bool


@dataclass(frozen=True, slots=True)
class ResumeEntry:
    """One human-readable entry inside a resume section."""

    heading: str
    subheading: str | None = None
    meta: str | None = None
    body: str | None = None
    bullets: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ResumeSection:
    """One ordered ATS-safe resume section."""

    title: str
    entries: list[ResumeEntry] = field(default_factory=list)
    inline_items: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RenderedResume:
    """Exporter-neutral resume content derived from an approved draft."""

    full_name: str
    target_role: str
    contact_items: list[str]
    summary: str
    sections: list[ResumeSection]
    style: ResumeStyle
