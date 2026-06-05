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
            skills_section=[
                {"category": "Languages", "skills": ["Python", "SQL"]},
                {"category": "Backend", "skills": ["FastAPI", "PostgreSQL"]},
            ],
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
            [section.title for section in rendered.sections][:3],
            ["Skills", "Projects", "Experience"],
        )
        self.assertIn("# Ada Lovelace", markdown)
        self.assertIn("Languages: Python, SQL", markdown)
        self.assertIn("Backend: FastAPI, PostgreSQL", markdown)
        self.assertNotIn("Languages: Python, SQL, Backend", markdown)
        self.assertNotIn("Kubernetes", markdown)
        self.assertNotIn("truthfulness", markdown.lower())

    def test_modern_professional_template_uses_ats_section_order(self) -> None:
        rendered = get_resume_template(ResumeTemplateName.MODERN_PROFESSIONAL).render(
            self.draft, self.candidate
        )

        self.assertEqual(rendered.sections[0].title, "Skills")
        self.assertTrue(rendered.style.section_divider)

    def test_additional_experience_renders_as_separate_section(self) -> None:
        self.draft.experience_section.append(
            {
                "job_title": "Online Tutor and Learning Operations Lead",
                "company": "Ignite Learning",
                "start_date": "2018-01-01",
                "description": "Runs an online tutoring service.",
                "achievements": ["Manages student communication and scheduling."],
                "is_additional": True,
            }
        )
        rendered = get_resume_template(ResumeTemplateName.CLEAN_ATS).render(
            self.draft,
            self.candidate,
        )
        markdown = MarkdownRenderer().render(rendered)

        self.assertIn("## Experience", markdown)
        self.assertIn("## Additional Experience", markdown)
        self.assertIn("Online Tutor and Learning Operations Lead", markdown)

    def test_request_rejects_unsupported_output_format(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentGenerationRequest(
                resume_draft_id=uuid4(),
                output_format="rtf",
            )


if __name__ == "__main__":
    unittest.main()
