"""Unit tests for ATS-safe document-generation templates and schemas."""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.features.document_generation.renderers import MarkdownRenderer
from app.features.document_generation.templates import get_resume_template
from app.models import CandidateProfile, ResumeDraft
from app.models.enums import ResumeTemplateName
from app.schemas import DocumentGenerationRequest


class DocumentGenerationTemplateTests(unittest.TestCase):
    """Verify template ordering, truthfulness boundaries, and request validation."""

    def setUp(self) -> None:
        self.candidate = CandidateProfile(
            full_name="Ada Lovelace",
            email="ada@example.com",
            location="London",
        )
        self.draft = ResumeDraft(
            resume_analysis_id=uuid4(),
            candidate_profile_id=uuid4(),
            job_analysis_id=uuid4(),
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Backend engineer with evidence-backed Python experience.",
            skills_section=[{"name": "Python", "category": "Programming"}],
            experience_section=[
                {
                    "job_title": "Software Engineer",
                    "company": "Analytical Engines",
                    "start_date": "2022-01-01",
                    "description": "Built reliable Python services.",
                    "achievements": ["Improved delivery reliability"],
                }
            ],
            projects_section=[
                {
                    "title": "Commerce API",
                    "technologies": ["Python", "FastAPI"],
                    "description": "Built a commerce API.",
                    "outcomes": ["Reduced processing time"],
                }
            ],
            truthfulness_notes=["Do not claim Kubernetes."],
            omitted_keywords=["Kubernetes"],
        )

    def test_clean_ats_template_is_single_column_and_omits_internal_notes(self) -> None:
        rendered = get_resume_template(ResumeTemplateName.CLEAN_ATS).render(
            self.draft, self.candidate
        )
        markdown = MarkdownRenderer().render(rendered)

        self.assertEqual(
            [section.title for section in rendered.sections][:2], ["Skills", "Experience"]
        )
        self.assertIn("# Ada Lovelace", markdown)
        self.assertIn("Python", markdown)
        self.assertNotIn("Kubernetes", markdown)
        self.assertNotIn("truthfulness", markdown.lower())

    def test_modern_professional_template_prioritizes_experience(self) -> None:
        rendered = get_resume_template(ResumeTemplateName.MODERN_PROFESSIONAL).render(
            self.draft, self.candidate
        )

        self.assertEqual(rendered.sections[0].title, "Experience")
        self.assertTrue(rendered.style.section_divider)

    def test_request_rejects_unsupported_output_format(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentGenerationRequest(
                resume_draft_id=uuid4(),
                output_format="rtf",
            )


if __name__ == "__main__":
    unittest.main()
