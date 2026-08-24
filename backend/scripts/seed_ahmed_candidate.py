"""Seed Ahmed Raza's real early-career candidate profile for local testing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from os import environ

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import create_database_engine, create_session_factory, session_scope
from app.models.enums import RelocationPreference, RemotePreference, ResumeStyle
from app.schemas import (
    CandidateProfileCreate,
    CandidateProfileRead,
    CareerGoalCreate,
    CertificationCreate,
    EducationCreate,
    PreferenceCreate,
    ProjectCreate,
    SkillCreate,
    WorkExperienceCreate,
)
from app.services import KnowledgeBaseService
from scripts.demo_user import DEMO_EMAIL, DEMO_PASSWORD, get_or_create_demo_user

SKILLS = [
    ("Python", "Programming Languages", 4, "2.00"),
    ("FastAPI", "Backend Development", 4, "1.50"),
    ("PostgreSQL", "Databases", 3, "1.50"),
    ("SQL", "Databases", 3, "1.75"),
    ("Playwright", "Browser Automation", 4, "1.25"),
    ("APIs", "Backend Development", 4, "1.75"),
    ("Webhooks", "Workflow Automation", 3, "1.25"),
    ("Docker", "Developer Tools", 3, "1.25"),
    ("GitHub", "Developer Tools", 4, "2.00"),
    ("Google Cloud", "Cloud and ML Platforms", 3, "1.00"),
    ("Vertex AI", "Cloud and ML Platforms", 3, "0.75"),
    ("BigQuery ML", "Cloud and ML Platforms", 3, "0.75"),
    ("Machine Learning", "AI Engineering", 4, "2.00"),
    ("Deep Learning", "AI Engineering", 3, "1.50"),
    ("Neural Networks", "AI Engineering", 3, "1.50"),
    ("Computer Vision", "AI Engineering", 3, "1.25"),
    ("Reinforcement Learning", "AI Engineering", 3, "1.00"),
    ("MLOps", "AI Engineering", 3, "1.00"),
    ("DataOps", "Data Engineering", 3, "0.75"),
    ("DevOps basics", "Developer Tools", 3, "1.00"),
    ("Automation", "Workflow Automation", 4, "1.50"),
    ("Resume automation", "Career Automation", 4, "1.00"),
    ("Job extraction", "Career Automation", 4, "1.00"),
    ("Document generation", "Career Automation", 4, "1.00"),
]

DEVELOPER_EMAIL = environ.get("CAREEROS_DEVELOPER_EMAIL", "ahmed.raza@example.com")
DEVELOPER_PHONE = environ.get("CAREEROS_DEVELOPER_PHONE") or None


def seed_ahmed_candidate(session: Session) -> CandidateProfileRead:
    """Create Ahmed Raza's complete early-career profile through application services."""
    service = KnowledgeBaseService(session)
    demo_user = get_or_create_demo_user(session)
    profile = service.create_candidate_profile(
        CandidateProfileCreate(
            full_name="Ahmed Raza",
            email=DEVELOPER_EMAIL,
            phone=DEVELOPER_PHONE,
            headline="Early-Career AI Engineer and AI Automation Developer",
            summary=(
                "Bachelor of Artificial Intelligence candidate with hands-on project "
                "experience in Python, FastAPI, PostgreSQL, Playwright job extraction, "
                "resume automation, document generation, and Google Cloud machine-learning "
                "coursework. Technical experience is represented through projects, "
                "certifications, and early-career engineering practice."
            ),
            location="Islamabad, Pakistan",
            linkedin_url="https://www.linkedin.com/in/ahmed-raza-kahoot/",
            portfolio_url="https://github.com/7-ARK",
        ),
        user_id=demo_user.id,
    )

    service.add_education(
        profile.id,
        EducationCreate(
            institution="Bahria University Islamabad",
            degree="Bachelor of Artificial Intelligence",
            field_of_study="Artificial Intelligence",
            start_date=date(2021, 9, 1),
            end_date=date(2025, 6, 30),
            description=(
                "Studied artificial intelligence, machine learning, deep learning, neural "
                "networks, computer vision, reinforcement learning, and software development."
            ),
        ),
    )
    service.add_experience(
        profile.id,
        WorkExperienceCreate(
            company="Ignite Learning",
            job_title="Online Tutor and Learning Operations Lead",
            employment_type="Self-employed",
            location="Remote",
            start_date=date(2018, 1, 1),
            is_current=True,
            description=(
                "Provides online tutoring services to students worldwide and runs an online "
                "tutoring business. This is business, teaching, and operations experience, not "
                "software engineering employment."
            ),
            achievements=[
                "Tutors O/A Levels, IGCSE, GCSE, Edexcel, AQA, and AP students.",
                "Teaches Mathematics, Physics, and English across international programs.",
                "Manages student communication, scheduling, service delivery, and operations.",
                (
                    "Builds practical experience with remote work, client communication, "
                    "and business ownership."
                ),
            ],
        ),
    )

    for project in _projects():
        service.add_project(profile.id, project)
    for name, category, rating, years in SKILLS:
        service.add_skill(
            profile.id,
            SkillCreate(
                name=name,
                category=category,
                self_rating=rating,
                years_of_experience=Decimal(years),
            ),
        )
    for certification in _certifications():
        service.add_certification(profile.id, certification)

    service.update_career_goals(
        profile.id,
        CareerGoalCreate(
            target_roles=[
                "AI Automation Engineer",
                "AI Engineer",
                "Machine Learning Engineer Intern",
                "Python Backend Developer",
                "GenAI Engineer Intern",
                "MLOps Intern",
                "AI Workflow Developer",
            ],
            preferred_industries=[
                "AI Products",
                "Workflow Automation",
                "Developer Tools",
                "Education Technology",
                "Cloud and Machine Learning Platforms",
            ],
            remote_preference=RemotePreference.REMOTE,
            relocation_preference=RelocationPreference.CONDITIONAL,
            geographic_preferences=[
                "Remote",
                "United States",
                "Canada",
                "Europe",
                "Worldwide",
            ],
        ),
    )
    service.update_preferences(
        profile.id,
        PreferenceCreate(
            resume_style=ResumeStyle.ATS_FOCUSED,
            resume_preferences={
                "preferred_length_pages": 1,
                "emphasize_projects": True,
                "emphasize_certifications": True,
                "avoid_senior_claims": True,
                "separate_tutoring_from_engineering": True,
            },
            application_preferences={
                "target_levels": ["internship", "junior", "entry_level"],
                "preferred_workplace_types": ["remote"],
                "regions": ["US", "Canada", "Europe", "Worldwide"],
            },
            communication_preferences={
                "tone": "clear_professional",
                "truthfulness_rule": (
                    "Do not claim senior-level production software engineering experience "
                    "unless supported by candidate evidence."
                ),
            },
        ),
    )
    return service.get_profile(profile.id)


def seed_database(database_url: str) -> CandidateProfileRead:
    """Seed Ahmed's profile after Alembic initializes the configured database."""
    engine = create_database_engine(database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            return seed_ahmed_candidate(session)
    finally:
        engine.dispose()


def main() -> None:
    """Run Ahmed's seed workflow from `DATABASE_URL` and print its profile ID."""
    database_url = Settings.from_env().database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is required. Set it before running the seed script.")
    profile = seed_database(database_url)
    print("careerOS Ahmed Raza candidate created")
    print(f"demo_email={DEMO_EMAIL}")
    print(f"demo_password={DEMO_PASSWORD}")
    print(f"candidate_profile_id={profile.id}")
    print(f"candidate_name={profile.full_name}")
    print(
        f"skills={len(profile.skills)} projects={len(profile.projects)} "
        f"certifications={len(profile.certifications)}"
    )


def _certifications() -> list[CertificationCreate]:
    """Return Ahmed's certification records with compact topic notes."""
    return [
        CertificationCreate(
            name="Machine Learning on Google Cloud",
            issuing_organization="Google / Coursera",
            issue_date=date(2025, 1, 1),
            credential_id=(
                "Topics: Vertex AI AutoML, BigQuery ML, custom training jobs, Docker "
                "containers, Feature Store, feature engineering, data preprocessing"
            ),
            credential_url="https://coursera.org/verify/specialization/SP27BEQ0EOJH",
        ),
        CertificationCreate(
            name="Advanced Machine Learning on Google Cloud",
            issuing_organization="Google / Coursera",
            issue_date=date(2025, 2, 1),
            credential_id=(
                "Topics: scalable production ML, structured data, image data, time-series, "
                "NLP text, recommendation systems, computer vision fundamentals"
            ),
            credential_url="https://coursera.org/verify/specialization/QVB8OT7ZQAG4",
        ),
        CertificationCreate(
            name="DevOps, DataOps, MLOps",
            issuing_organization="Duke University",
            issue_date=date(2025, 3, 1),
            credential_id="Topics: DevOps, DataOps, MLOps, production workflows",
        ),
        CertificationCreate(
            name="MLOps Platforms: Amazon SageMaker and Azure ML",
            issuing_organization="Coursera",
            issue_date=date(2025, 3, 1),
            credential_id="Topics: Amazon SageMaker, Azure ML, managed MLOps platforms",
        ),
    ]


def _projects() -> list[ProjectCreate]:
    """Return project evidence for Ahmed's early-career technical profile."""
    return [
        ProjectCreate(
            title="careerOS",
            description=(
                "AI-powered career automation system that reads job postings, extracts job "
                "requirements, compares them with candidate profiles, generates tailored "
                "resumes, exports PDF documents, and tracks applications."
            ),
            technologies=[
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Playwright",
                "React/Vite",
                "Docker",
                "GitHub",
                "Automation",
            ],
            outcomes=[
                "Built URL and manual job-import flows for local testing.",
                "Generated tailored resume documents from candidate profile evidence.",
                "Tracked job, resume, and application records through backend services.",
            ],
            github_url="https://github.com/7-ARK/careerOS",
            start_date=date(2025, 11, 1),
        ),
        ProjectCreate(
            title="Legal Document OCR and Extraction System",
            description=(
                "Document-processing system for OCR and structured legal data extraction "
                "with validation and PostgreSQL-backed records."
            ),
            technologies=[
                "Python",
                "FastAPI",
                "OCR",
                "Structured extraction",
                "Validation",
                "PostgreSQL",
            ],
            outcomes=[
                "Extracted structured legal data from unstructured document text.",
                "Applied validation checks to improve reliability of extracted records.",
                "Built API-based backend services for document-processing workflows.",
            ],
            github_url="https://github.com/7-ARK",
            start_date=date(2025, 4, 1),
        ),
        ProjectCreate(
            title="AI Workflow Automation System",
            description=(
                "Workflow automation system using APIs, webhooks, and AI-assisted process "
                "orchestration concepts for repeatable task flows."
            ),
            technologies=[
                "Python",
                "APIs",
                "Webhooks",
                "Automation",
                "OpenAI API concepts",
                "LangGraph concepts",
            ],
            outcomes=[
                "Designed webhook-driven automation flows for repetitive processes.",
                "Connected API-based steps into reviewable workflow stages.",
                (
                    "Explored AI-assisted process orchestration without claiming production "
                    "agent experience."
                ),
            ],
            github_url="https://github.com/7-ARK",
            start_date=date(2025, 7, 1),
        ),
        ProjectCreate(
            title="IBM Dev Day / Ops Incident First Response Agent",
            description=(
                "Hackathon project for incident classification, ownership assignment, ticket "
                "creation, and response workflow."
            ),
            technologies=[
                "AI agents concept",
                "Workflow automation",
                "Slack-style notifications",
                "Service operations",
            ],
            outcomes=[
                "Designed a first-response workflow for classifying operational incidents.",
                "Mapped ownership assignment and ticket creation steps.",
                "Built hackathon evidence for service operations and workflow automation concepts.",
            ],
            github_url="https://github.com/7-ARK",
            start_date=date(2025, 10, 1),
        ),
    ]


if __name__ == "__main__":
    main()
