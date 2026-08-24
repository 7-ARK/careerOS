"""Focused coverage for local, review-first resume extraction."""

from io import BytesIO

import pytest
from docx import Document

from app.features.resume_import import ResumeImportError, parse_resume


def test_docx_import_builds_reviewable_profile_without_skill_misclassification() -> None:
    document = Document()
    for line in (
        "Ahmed Khan",
        "Applied AI Engineer",
        "ahmed@example.com | +92 300 1234567",
        "https://github.com/ahmed | https://linkedin.com/in/ahmed",
        "Professional Summary",
        "Builds evidence-grounded AI and backend workflows.",
        "Skills",
        "Python, APIs, RAG, LangChain, LangGraph, GitHub",
        "Experience",
        "Software Engineer | Example Labs | Jan 2023 - Present",
        "Projects",
        "CareerOS | Evidence-grounded career workflow | Python, FastAPI, RAG",
        "Education",
        "BS Computer Science | Example University | 2023",
    ):
        document.add_paragraph(line)
    content = BytesIO()
    document.save(content)

    preview = parse_resume("Ahmed_Resume.docx", content.getvalue())

    assert preview.requires_review is True
    assert preview.profile.full_name == "Ahmed Khan"
    assert preview.profile.email == "ahmed@example.com"
    skills = {item.name: item.category for item in preview.profile.skills}
    assert skills["Python"] == "Languages"
    assert skills["APIs"] == "Backend"
    assert skills["RAG"] == "AI / Machine Learning"
    assert skills["GitHub"] == "Developer Tools"
    assert preview.profile.work_experiences[0].start_date.isoformat() == "2023-01-01"
    assert preview.profile.work_experiences[0].is_current is True
    assert preview.profile.education[0].field_of_study is None
    assert "original resume was not stored" in preview.warnings[0]


def test_resume_import_rejects_wrong_extension_and_empty_content() -> None:
    with pytest.raises(ResumeImportError, match="empty"):
        parse_resume("resume.pdf", b"")
    with pytest.raises(ResumeImportError, match="PDF or DOCX"):
        parse_resume("resume.txt", b"plain text")
