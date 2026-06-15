"""Tests for deterministic resume quality shaping."""

import unittest
from datetime import date
from decimal import Decimal

from app.features.resume_intelligence.llm import LLMResumeQualityService
from app.features.resume_intelligence.quality import DeterministicResumeQualityEngine
from app.repositories import CandidateProfileRepository
from app.schemas import (
    CandidateProfileCreate,
    CertificationCreate,
    JobDescriptionCreate,
    ProjectCreate,
    SkillCreate,
    WorkExperienceCreate,
)
from app.services import JobAnalysisService, KnowledgeBaseService, ResumeIntelligenceService
from tests.support import create_test_engine, create_test_session, create_test_user

AI_JOB_DESCRIPTION = """
AI Engineer contract role building API-driven AI solutions, automation workflows,
LLM integrations, OpenAI platform work, LangChain orchestration, production Python
systems, microservices, and workflow automation.
"""

AI_AUTOMATION_JOB = """
We are looking for an AI Automation Engineer to build internal AI-powered workflows and
business automation systems.

Requirements:
- Python
- FastAPI
- OpenAI APIs
- Workflow automation
- API integrations
- Webhooks
- Playwright
- n8n or Make
- PostgreSQL
- Docker

Responsibilities:
- Build automation systems
- Design workflow pipelines
- Integrate APIs
- Create AI-assisted internal tools
- Maintain backend services
- Improve operational efficiency
"""

LEGAL_AI_JOB = """
We are hiring a Legal AI Engineer to build document-processing systems for legal workflows.

Requirements:
- OCR
- Document extraction
- Structured data extraction
- FastAPI
- PostgreSQL
- Validation systems
- Legal technology
- AI-assisted document review

Responsibilities:
- Build legal document pipelines
- Extract structured data from legal filings
- Improve document validation
- Create backend APIs
- Support legal workflow automation
"""

BACKEND_PYTHON_JOB = """
We are seeking a Backend Python Engineer.

Requirements:
- Python
- FastAPI
- REST APIs
- PostgreSQL
- Docker
- GitHub
- CI/CD
- Backend architecture

Responsibilities:
- Build backend services
- Create APIs
- Maintain databases
- Improve deployment workflows
- Work with engineering teams
"""

MACHINE_LEARNING_JOB = """
We are looking for a Machine Learning Engineer.

Requirements:
- Machine Learning
- Deep Learning
- Neural Networks
- Computer Vision
- Reinforcement Learning
- Google Cloud
- Vertex AI
- BigQuery ML
- MLOps
- Python

Responsibilities:
- Train ML models
- Build ML pipelines
- Deploy ML workloads
- Work with cloud-based ML systems
- Support experimentation and model evaluation
"""


class ResumeQualityEngineTests(unittest.TestCase):
    """Verify deterministic project selection and resume draft shaping."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        knowledge_base = KnowledgeBaseService(self.session)
        user = create_test_user(self.session)
        profile = knowledge_base.create_candidate_profile(
            CandidateProfileCreate(
                full_name="Ahmed Raza",
                headline="Early-Career AI Engineer and AI Automation Developer",
            ),
            user_id=user.id,
        )
        for name, category in (
            ("Python", "Programming Languages"),
            ("SQL", "Databases"),
            ("FastAPI", "Backend Development"),
            ("PostgreSQL", "Databases"),
            ("OpenAI API", "AI Engineering"),
            ("LangGraph", "AI Engineering"),
            ("Playwright", "Browser Automation"),
            ("Docker", "Developer Tools"),
            ("GitHub", "Developer Tools"),
            ("Automation", "Workflow Automation"),
            ("Webhooks", "Workflow Automation"),
            ("Google Cloud", "Cloud and ML Platforms"),
            ("Vertex AI", "Cloud and ML Platforms"),
            ("BigQuery ML", "Cloud and ML Platforms"),
            ("Machine Learning", "AI Engineering"),
            ("Deep Learning", "AI Engineering"),
            ("Neural Networks", "AI Engineering"),
            ("Computer Vision", "AI Engineering"),
            ("Reinforcement Learning", "AI Engineering"),
            ("MLOps", "AI Engineering"),
        ):
            knowledge_base.add_skill(
                profile.id,
                SkillCreate(
                    name=name,
                    category=category,
                    self_rating=4,
                    years_of_experience=Decimal("1.50"),
                ),
            )
        for project in _projects():
            knowledge_base.add_project(profile.id, project)
        knowledge_base.add_certification(
            profile.id,
            CertificationCreate(
                name="Machine Learning on Google Cloud",
                issuing_organization="Google / Coursera",
                credential_id="Topics: Vertex AI, BigQuery ML, MLOps, production ML concepts",
            ),
        )
        knowledge_base.add_experience(
            profile.id,
            WorkExperienceCreate(
                company="Ignite Learning",
                job_title="Online Tutor and Learning Operations Lead",
                start_date=date(2018, 1, 1),
                is_current=True,
                description="Runs an online tutoring business for international students.",
                achievements=["Manages communication, scheduling, and academic support."],
            ),
        )
        self.profile_id = profile.id
        self.job_analysis = JobAnalysisService(self.session).analyze_and_store(
            JobDescriptionCreate(
                raw_title="AI Engineer",
                company_name="AI Studio",
                description_text=AI_JOB_DESCRIPTION,
            )
        )

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_selects_relevant_projects_above_lower_relevance_ocr_project(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        selection = DeterministicResumeQualityEngine().select_projects(
            candidate,
            self.job_analysis,
        )

        selected_titles = [score.project.title for score in selection.selected]
        excluded_titles = [score.project.title for score in selection.excluded]

        self.assertEqual(len(selected_titles), 3)
        self.assertIn("careerOS", selected_titles)
        self.assertIn("AI Workflow Automation System", selected_titles)
        self.assertIn("IBM Dev Day / Ops Incident First Response Agent", selected_titles)
        self.assertIn("Legal Document OCR and Extraction System", excluded_titles)

    def test_resume_draft_uses_grouped_skills_and_selected_projects_only(self) -> None:
        service = ResumeIntelligenceService(
            self.session,
            quality_engine=DeterministicResumeQualityEngine(),
        )
        analysis = service.analyze_candidate_for_job(self.profile_id, self.job_analysis.id)
        draft = service.create_resume_draft_from_analysis(analysis.analysis.id)

        project_titles = [project["title"] for project in draft.projects_section]
        skill_categories = [group["category"] for group in draft.skills_section]

        self.assertEqual(len(draft.projects_section), 3)
        self.assertIn("careerOS", project_titles)
        self.assertNotIn("Legal Document OCR and Extraction System", project_titles)
        self.assertIn("Languages", skill_categories)
        self.assertIn("Backend", skill_categories)
        self.assertIn("AI / Machine Learning", skill_categories)
        self.assertNotIn("Kubernetes", draft.summary)
        self.assertNotIn("knowledge-base evidence", draft.summary)
        self.assertLessEqual(len(draft.skills_section), 5)
        self.assertTrue(all(len(project["outcomes"]) <= 3 for project in draft.projects_section))
        self.assertTrue(
            all(
                certification["credential_id"] is None
                for certification in draft.certifications_section
            )
        )
        self.assertFalse(
            any(experience.get("is_additional") for experience in draft.experience_section)
        )

    def test_llm_disabled_uses_deterministic_fallback(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=False,
            api_key="test-key",
            model="gpt-4.1-mini",
            client=FailingClient(),
        ).build(candidate, self.job_analysis, analysis)

        self.assertFalse(quality.warnings)
        self.assertIn("hands-on project experience", quality.summary)

    def test_missing_openai_key_uses_fallback_with_warning(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=True,
            api_key=None,
            model="gpt-4.1-mini",
        ).build(candidate, self.job_analysis, analysis)

        self.assertIn("OPENAI_API_KEY is missing", quality.warnings[0])

    def test_openai_failure_uses_fallback_with_warning(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=True,
            api_key="test-key",
            model="gpt-4.1-mini",
            client=FailingClient(),
        ).build(candidate, self.job_analysis, analysis)

        self.assertIn("deterministic fallback", quality.warnings[0])

    def test_llm_output_is_filtered_to_candidate_evidence(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=True,
            api_key="test-key",
            model="gpt-4.1-mini",
            client=SuccessfulClient(),
        ).build(candidate, self.job_analysis, analysis)

        grouped_skills = [
            skill for group in quality.skills_section for skill in group.get("skills", [])
        ]
        self.assertIn("Python", grouped_skills)
        self.assertNotIn("Kubernetes", grouped_skills)
        self.assertIn("Human summary", quality.summary)
        self.assertTrue(
            any(
                "LLM-supported project reason" in str(project["reason"])
                for project in quality.selected_projects
            )
        )

    def test_llm_project_scores_can_rerank_known_projects(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=True,
            api_key="test-key",
            model="gpt-4.1-mini",
            client=ProjectRerankingClient(),
        ).build(candidate, self.job_analysis, analysis)

        selected_titles = [project["title"] for project in quality.selected_projects]
        self.assertIn("Legal Document OCR and Extraction System", selected_titles)
        self.assertLessEqual(len(selected_titles), 3)

    def test_llm_summary_rejects_unsupported_production_claims(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        analysis = (
            ResumeIntelligenceService(self.session)
            .analyze_candidate_for_job(
                self.profile_id,
                self.job_analysis.id,
            )
            .analysis
        )
        quality = LLMResumeQualityService(
            enabled=True,
            api_key="test-key",
            model="gpt-4.1-mini",
            client=UnsafeSummaryClient(),
        ).build(candidate, self.job_analysis, analysis)

        self.assertNotIn("production GCP deployment", quality.summary)
        self.assertTrue(
            any("unsupported production claim" in warning for warning in quality.warnings)
        )

    def test_gcp_certification_warning_is_nuanced(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        warnings = ResumeIntelligenceService(self.session).engine.generate_truthfulness_warnings(
            [],
            ["GCP"],
            [],
            [],
            ResumeIntelligenceService(self.session).engine.collect_evidence(candidate),
        )

        self.assertIn("Can mention Google Cloud ML certifications", warnings[0])
        self.assertIn("avoid claiming production GCP deployment", warnings[0])

    def test_careeros_boost_only_applies_when_job_is_relevant(self) -> None:
        candidate = CandidateProfileRepository(self.session).get_complete(self.profile_id)
        careeros = next(project for project in candidate.projects if project.title == "careerOS")
        relevant_score = (
            DeterministicResumeQualityEngine()
            .score_project(
                careeros,
                self.job_analysis,
            )
            .score
        )
        unrelated_analysis = JobAnalysisService(self.session).analyze_and_store(
            JobDescriptionCreate(
                raw_title="Retail Sales Associate",
                company_name="Storefront",
                description_text="Assist customers, organize inventory, and operate checkout.",
            )
        )
        unrelated_score = (
            DeterministicResumeQualityEngine()
            .score_project(
                careeros,
                unrelated_analysis,
            )
            .score
        )

        self.assertGreater(relevant_score, unrelated_score)

    def test_ai_automation_role_selects_automation_projects_and_excludes_legal_ocr(self) -> None:
        draft = self._draft_for_job("AI Automation Engineer", AI_AUTOMATION_JOB)
        project_titles = [project["title"] for project in draft.projects_section]
        skill_categories = [group["category"] for group in draft.skills_section]

        self.assertIn("careerOS", project_titles)
        self.assertIn("AI Workflow Automation System", project_titles)
        self.assertIn("IBM Dev Day / Ops Incident First Response Agent", project_titles)
        self.assertNotIn("Legal Document OCR and Extraction System", project_titles)
        self.assertLess(project_titles.index("careerOS"), 2)
        self.assertIn("Automation", skill_categories)
        self.assertIn("Backend", skill_categories)

    def test_legal_ai_role_ranks_legal_ocr_first_and_mentions_document_workflows(self) -> None:
        draft = self._draft_for_job("Legal AI Engineer", LEGAL_AI_JOB)
        project_titles = [project["title"] for project in draft.projects_section]
        skill_categories = [group["category"] for group in draft.skills_section]

        self.assertEqual(project_titles[0], "Legal Document OCR and Extraction System")
        self.assertIn("careerOS", project_titles)
        self.assertIn("Document AI / Extraction", skill_categories)
        self.assertIn("document extraction", draft.summary.casefold())
        self.assertIn("legal workflow", draft.summary.casefold())

    def test_backend_python_role_prioritizes_backend_and_reduces_ai_noise(self) -> None:
        draft = self._draft_for_job("Backend Python Engineer", BACKEND_PYTHON_JOB)
        project_titles = [project["title"] for project in draft.projects_section]
        skill_categories = [group["category"] for group in draft.skills_section]

        self.assertEqual(
            project_titles[:3],
            [
                "careerOS",
                "Legal Document OCR and Extraction System",
                "AI Workflow Automation System",
            ],
        )
        self.assertIn("Backend", skill_categories)
        self.assertIn("Databases", skill_categories)
        self.assertNotIn("AI / Machine Learning", skill_categories)
        self.assertIn("backend", draft.summary.casefold())
        self.assertIn("api", draft.summary.casefold())

    def test_machine_learning_role_prioritizes_ml_cloud_and_reduces_automation_noise(self) -> None:
        draft = self._draft_for_job("Machine Learning Engineer", MACHINE_LEARNING_JOB)
        skill_categories = [group["category"] for group in draft.skills_section]
        skill_text = " ".join(
            skill for group in draft.skills_section for skill in group.get("skills", [])
        )

        self.assertIn("AI / Machine Learning", skill_categories)
        self.assertIn("Cloud / MLOps", skill_categories)
        self.assertLess(skill_categories.index("AI / Machine Learning"), 2)
        self.assertIn("Vertex AI", skill_text)
        self.assertIn("BigQuery ML", skill_text)
        self.assertIn("MLOps", skill_text)
        certification_names = " ".join(cert["name"] for cert in draft.certifications_section)
        self.assertIn("Google Cloud", certification_names)
        self.assertIn("machine learning", draft.summary.casefold())
        self.assertNotIn("production gcp deployment", draft.summary.casefold())

    def _draft_for_job(self, raw_title: str, description: str):
        """Create a deterministic resume draft for one manual test job."""
        job_analysis = JobAnalysisService(self.session).analyze_and_store(
            JobDescriptionCreate(
                raw_title=raw_title,
                company_name="Test Company",
                description_text=description,
            )
        )
        service = ResumeIntelligenceService(
            self.session,
            quality_engine=DeterministicResumeQualityEngine(),
        )
        analysis = service.analyze_candidate_for_job(self.profile_id, job_analysis.id)
        return service.create_resume_draft_from_analysis(analysis.analysis.id)


def _projects() -> list[ProjectCreate]:
    """Build project fixtures with intentional relevance differences."""
    return [
        ProjectCreate(
            title="careerOS",
            description=(
                "AI career automation product using Python, FastAPI, Playwright, APIs, "
                "resume automation, document generation, and application tracking."
            ),
            technologies=["Python", "FastAPI", "PostgreSQL", "Playwright", "Automation"],
            outcomes=[
                "Built URL and manual job import flows.",
                "Generated tailored PDF resume documents.",
                "Tracked application records.",
                "Built backend services.",
                "Generated noisy duplicate outcome.",
            ],
            github_url="https://github.com/7-ARK/careerOS",
        ),
        ProjectCreate(
            title="AI Workflow Automation System",
            description="Workflow automation system using APIs, webhooks, and OpenAI concepts.",
            technologies=["Python", "APIs", "Webhooks", "Automation", "LangGraph"],
            outcomes=["Automated repetitive workflows.", "Connected API workflow stages."],
            github_url="https://github.com/7-ARK",
        ),
        ProjectCreate(
            title="IBM Dev Day / Ops Incident First Response Agent",
            description=(
                "Hackathon project for AI agent incident classification and response workflow."
            ),
            technologies=["AI agents concept", "Workflow automation", "Service operations"],
            outcomes=["Designed incident classification flow.", "Mapped ownership assignment."],
            github_url="https://github.com/7-ARK",
        ),
        ProjectCreate(
            title="Legal Document OCR and Extraction System",
            description="Document-processing system for OCR and structured legal data extraction.",
            technologies=["Python", "FastAPI", "OCR", "PostgreSQL"],
            outcomes=["Extracted structured legal data.", "Applied validation checks."],
            github_url="https://github.com/7-ARK",
        ),
    ]


class FailingClient:
    """Fake OpenAI client that always fails."""

    def create_json_response(self, **_: object) -> dict[str, object]:
        """Raise a deterministic failure."""
        raise RuntimeError("simulated OpenAI failure")


class SuccessfulClient:
    """Fake OpenAI client that returns structured resume-quality JSON."""

    def create_json_response(self, **_: object) -> dict[str, object]:
        """Return a deterministic structured response."""
        return {
            "professional_summary": "Human summary grounded in project evidence.",
            "skill_groups": [
                {"name": "Languages", "skills": ["Python", "SQL", "Kubernetes"]},
                {"name": "Backend", "skills": ["FastAPI", "PostgreSQL"]},
            ],
            "selected_projects": [
                {
                    "project_name": "careerOS",
                    "reason": "LLM-supported project reason.",
                    "support_level": "supported",
                    "relevance_score": 90,
                }
            ],
            "excluded_projects": [
                {
                    "project_name": "Legal Document OCR and Extraction System",
                    "reason": "Lower relevance for this role.",
                    "support_level": "supported",
                    "relevance_score": 20,
                }
            ],
            "resume_strategy_notes": [
                {"note": "Do not claim production agents.", "support_level": "unsupported"}
            ],
            "truthfulness_warnings": ["Do not claim production Kubernetes experience."],
            "cloud_certification_notes": [
                "Can mention Google Cloud ML coursework; avoid production deployment claims."
            ],
        }


class UnsafeSummaryClient(SuccessfulClient):
    """Fake client that tries to insert an unsupported production claim."""

    def create_json_response(self, **kwargs: object) -> dict[str, object]:
        """Return a valid response with an unsafe summary."""
        response = super().create_json_response(**kwargs)
        response["professional_summary"] = "Built production GCP deployment pipelines."
        return response


class ProjectRerankingClient(SuccessfulClient):
    """Fake client that strongly promotes a known project."""

    def create_json_response(self, **kwargs: object) -> dict[str, object]:
        """Return scores that should move Legal OCR into the selected set."""
        response = super().create_json_response(**kwargs)
        response["selected_projects"] = [
            {
                "project_name": "Legal Document OCR and Extraction System",
                "reason": "Semantic score says this project is relevant.",
                "support_level": "supported",
                "relevance_score": 100,
            }
        ]
        response["excluded_projects"] = []
        return response


if __name__ == "__main__":
    unittest.main()
