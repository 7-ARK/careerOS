"""Code-based ATS-safe resume templates."""

from app.features.document_generation.templates.base import (
    RenderedResume,
    ResumeEntry,
    ResumeSection,
    ResumeStyle,
)
from app.features.document_generation.templates.resumes import get_resume_template

__all__ = [
    "RenderedResume",
    "ResumeEntry",
    "ResumeSection",
    "ResumeStyle",
    "get_resume_template",
]
