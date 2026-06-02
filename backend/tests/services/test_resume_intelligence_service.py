"""Service tests for evidence-backed resume analysis and drafting."""

import unittest
from datetime import date
from decimal import Decimal

from app.models.enums import ResumeDraftStatus, ResumeSectionType
from app.schemas import (
    CandidateProfileCreate,
    CertificationCreate,
    EducationCreate,
    JobDescriptionCreate,
    ProjectCreate,
    SkillCreate,
    WorkExperienceCreate,
)
from app.services import JobAnalysisService, KnowledgeBaseService, ResumeIntelligenceService
from tests.support import create_test_engine, create_test_session

TARGET_JOB = """
Responsibilities:
- Build backend development services and REST APIs.
- Design reliable cloud workflows.

Requirements:
- 4+ years of experience in backend development.
- Strong Python, FastAPI, PostgreSQL, Docker, and Kubernetes experience.

Preferred qualifications:
- OpenAI experience is a plus.
"""


class ResumeIntelligenceServiceTests(unittest.TestCase):
    """Verify deterministic scoring, evidence tracing, warnings, and draft creation."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        knowledge_base = KnowledgeBaseService(self.session)
        profile = knowledge_base.create_candidate_profile(
            CandidateProfileCreate(
                full_name="Grace Hopper",
                headline="Backend Engineer",
                summary="Engineer focused on reliable backend systems.",
            )
        )
        knowledge_base.add_skill(
            profile.id,
            SkillCreate(
                name="Python",
                category="Programming",
                self_rating=5,
                years_of_experience=Decimal("6"),
            ),
        )
        knowledge_base.add_skill(
            profile.id,
            SkillCreate(
                name="FastAPI",
                category="Framework",
                self_rating=4,
                years_of_experience=Decimal("3"),
            ),
        )
        knowledge_base.add_project(
            profile.id,
            ProjectCreate(
                title="Commerce API",
                description="Built REST APIs for a commerce platform.",
                technologies=["Python", "FastAPI", "PostgreSQL", "Docker"],
                outcomes=["Improved API reliability"],
            ),
        )
        knowledge_base.add_experience(
            profile.id,
            WorkExperienceCreate(
                company="Example Corp",
                job_title="Backend Engineer",
                start_date=date(2020, 1, 1),
                description="Built backend development services using Python and PostgreSQL.",
                achievements=["Delivered reliable REST APIs"],
            ),
        )
        knowledge_base.add_education(
            profile.id,
            EducationCreate(
                institution="Example University",
                degree="BS Computer Science",
            ),
        )
        knowledge_base.add_certification(
            profile.id,
            CertificationCreate(
                name="AWS Certified Developer",
                issuing_organization="Amazon Web Services",
            ),
        )
        job_service = JobAnalysisService(self.session)
        job_analysis = job_service.analyze_and_store(
            JobDescriptionCreate(
                raw_title="Senior Backend Engineer",
                company_name="Platform Labs",
                description_text=TARGET_JOB,
            )
        )
        self.profile_id = profile.id
        self.job_analysis_id = job_analysis.id
        self.service = ResumeIntelligenceService(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_calculates_keyword_skill_and_technology_coverage(self) -> None:
        keyword_coverage = self.service.calculate_keyword_coverage(
            self.profile_id, self.job_analysis_id
        )
        skill_coverage = self.service.calculate_skill_coverage(
            self.profile_id, self.job_analysis_id
        )
        technology_coverage = self.service.calculate_technology_coverage(
            self.profile_id, self.job_analysis_id
        )

        self.assertIn("Python", keyword_coverage.matched_keywords)
        self.assertIn("Backend Development", skill_coverage["matched"])
        self.assertIn("FastAPI", technology_coverage["matched"])
        self.assertIn("Kubernetes", technology_coverage["missing"])

    def test_analysis_persists_evidence_backed_recommendations_and_warnings(self) -> None:
        result = self.service.analyze_candidate_for_job(self.profile_id, self.job_analysis_id)

        self.assertGreater(result.analysis.overall_match_score, Decimal("0"))
        self.assertIn("Kubernetes", result.analysis.missing_technologies)
        self.assertTrue(result.analysis.relevant_projects)
        self.assertTrue(result.analysis.relevant_experiences)
        self.assertTrue(result.analysis.tailoring_recommendations)
        for recommendation in result.analysis.tailoring_recommendations:
            self.assertTrue(recommendation.evidence)
            self.assertNotIn("Kubernetes", recommendation.supported_keywords)
        self.assertTrue(
            any(
                "Do not claim Kubernetes" in warning
                for warning in result.analysis.truthfulness_warnings
            )
        )
        self.assertEqual(
            self.service.get_latest_resume_analysis(self.profile_id, self.job_analysis_id).id,
            result.analysis.id,
        )

    def test_exposes_strongest_evidence_and_missing_requirements(self) -> None:
        evidence = self.service.identify_strongest_evidence(self.profile_id, self.job_analysis_id)
        gaps = self.service.identify_missing_job_requirements(self.profile_id, self.job_analysis_id)

        self.assertTrue(evidence)
        self.assertTrue(
            all(
                item.source_type in {ResumeSectionType.EXPERIENCE, ResumeSectionType.PROJECTS}
                for item in evidence
            )
        )
        self.assertIn("Kubernetes", gaps["missing_required_technologies"])
        self.assertIn("OpenAI", gaps["unverified_preferred_technologies"])

    def test_create_resume_draft_uses_only_candidate_owned_facts(self) -> None:
        result = self.service.analyze_candidate_for_job(self.profile_id, self.job_analysis_id)
        draft = self.service.create_resume_draft_from_analysis(result.analysis.id)

        self.assertEqual(draft.target_role, "Senior Backend Engineer")
        self.assertTrue(draft.projects_section)
        self.assertTrue(draft.experience_section)
        self.assertIn("Kubernetes", draft.omitted_keywords)
        self.assertNotIn("Kubernetes", [skill["name"] for skill in draft.skills_section])
        self.assertTrue(any("Do not claim Kubernetes" in note for note in draft.truthfulness_notes))
        updated = self.service.update_resume_draft_status(draft.id, ResumeDraftStatus.REVIEWED)
        self.assertEqual(updated.status, ResumeDraftStatus.REVIEWED)
        self.assertEqual(len(self.service.list_resume_analyses_by_job(self.job_analysis_id)), 1)
        self.assertEqual(len(self.service.list_resume_drafts_by_job(self.job_analysis_id)), 1)

    def test_preferred_openai_without_evidence_is_a_truthfulness_warning(self) -> None:
        warnings = self.service.generate_truthfulness_warnings(
            self.profile_id, self.job_analysis_id
        )

        self.assertTrue(
            any("Preferred requirement OpenAI is unverified" in item for item in warnings)
        )
