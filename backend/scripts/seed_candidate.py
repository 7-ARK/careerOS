"""Seed a realistic early-career candidate for local pipeline testing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import Base, create_database_engine, create_session_factory, session_scope
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

SKILLS = [
    ("Python", "Programming Languages", 4, "2.50"),
    ("FastAPI", "Backend Development", 4, "1.75"),
    ("SQL", "Databases", 4, "2.00"),
    ("PostgreSQL", "Databases", 4, "1.75"),
    ("APIs", "Backend Development", 4, "2.00"),
    ("Webhooks", "Backend Development", 3, "1.50"),
    ("Playwright", "Browser Automation", 4, "1.50"),
    ("Selenium", "Browser Automation", 3, "1.25"),
    ("OpenAI API", "AI Engineering", 4, "1.75"),
    ("LangGraph", "AI Engineering", 3, "1.00"),
    ("LangChain", "AI Engineering", 3, "1.25"),
    ("RAG", "AI Engineering", 3, "1.25"),
    ("Docker", "Developer Tools", 3, "1.50"),
    ("GitHub", "Developer Tools", 4, "2.50"),
    ("Automation", "Workflow Automation", 4, "2.00"),
    ("n8n", "Workflow Automation", 3, "1.00"),
    ("Zapier", "Workflow Automation", 3, "1.25"),
]


def seed_candidate(session: Session) -> CandidateProfileRead:
    """Create one complete fictional candidate through the knowledge-base service."""
    service = KnowledgeBaseService(session)
    profile = service.create_candidate_profile(
        CandidateProfileCreate(
            full_name="Amina Rahman",
            email="amina.rahman.dev@example.com",
            phone="+1-555-014-0284",
            headline="AI Automation and Backend Developer",
            summary=(
                "Early-career backend developer focused on Python, FastAPI, AI-assisted "
                "workflow automation, structured-data extraction, and practical browser "
                "automation. Builds maintainable API services and evidence-backed automation "
                "tools for document and job workflows."
            ),
            location="Remote",
            linkedin_url="https://www.linkedin.com/in/amina-rahman-dev",
            portfolio_url="https://github.com/amina-rahman-dev",
        )
    )

    service.add_education(
        profile.id,
        EducationCreate(
            institution="Metro Institute of Technology",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
            start_date=date(2020, 9, 1),
            end_date=date(2024, 6, 30),
            description=(
                "Studied software engineering, databases, web development, and applied "
                "machine-learning fundamentals."
            ),
        ),
    )
    service.add_experience(
        profile.id,
        WorkExperienceCreate(
            company="Northstar Digital Studio",
            job_title="Junior Backend and Automation Developer",
            employment_type="Full-time",
            location="Remote",
            start_date=date(2024, 7, 1),
            is_current=True,
            description=(
                "Builds Python backend services and workflow automations for internal "
                "operations, document processing, and data collection."
            ),
            achievements=[
                "Built FastAPI endpoints and PostgreSQL-backed services for structured records.",
                "Automated repetitive workflows with APIs, webhooks, n8n, and Zapier.",
                "Integrated Playwright browser automation for authorized data-collection tasks.",
                "Added Docker-based local environments and GitHub pull-request workflows.",
            ],
        ),
    )
    service.add_experience(
        profile.id,
        WorkExperienceCreate(
            company="Civic Tech Lab",
            job_title="Software Automation Intern",
            employment_type="Internship",
            location="Hybrid",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            description=(
                "Supported a small engineering team building Python utilities for document "
                "processing and structured-data extraction."
            ),
            achievements=[
                "Extracted structured data from unstructured text and OCR output.",
                "Created SQL queries and validation checks for document-processing records.",
                "Wrote maintainable automation scripts and documented repeatable workflows.",
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

    service.add_certification(
        profile.id,
        CertificationCreate(
            name="Postman API Fundamentals Student Expert",
            issuing_organization="Postman",
            issue_date=date(2024, 8, 1),
        ),
    )
    service.update_career_goals(
        profile.id,
        CareerGoalCreate(
            target_roles=[
                "AI Automation Developer",
                "Python Developer",
                "Backend Developer",
                "FastAPI Developer",
                "AI Workflow Engineer",
            ],
            preferred_industries=[
                "Software",
                "AI Products",
                "Workflow Automation",
                "Developer Tools",
            ],
            salary_min=Decimal("55000"),
            salary_max=Decimal("85000"),
            salary_currency="USD",
            remote_preference=RemotePreference.FLEXIBLE,
            relocation_preference=RelocationPreference.CONDITIONAL,
            geographic_preferences=["Remote", "United States", "Canada"],
        ),
    )
    service.update_preferences(
        profile.id,
        PreferenceCreate(
            resume_style=ResumeStyle.ATS_FOCUSED,
            resume_preferences={
                "preferred_length_pages": 1,
                "prioritize_projects": True,
                "include_portfolio_links": True,
            },
            application_preferences={
                "create_application_record_by_default": True,
                "preferred_workplace_types": ["remote", "hybrid"],
            },
            communication_preferences={
                "tone": "concise_professional",
                "highlight_evidence": True,
            },
        ),
    )
    return service.get_profile(profile.id)


def seed_database(database_url: str) -> CandidateProfileRead:
    """Create required tables and seed one candidate in the configured database."""
    engine = create_database_engine(database_url)
    try:
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            return seed_candidate(session)
    finally:
        engine.dispose()


def main() -> None:
    """Run the local seed workflow from `DATABASE_URL` and print its profile ID."""
    database_url = Settings.from_env().database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is required. Set it before running the seed script.")
    profile = seed_database(database_url)
    print("careerOS development candidate created")
    print(f"candidate_profile_id={profile.id}")
    print(f"candidate_name={profile.full_name}")
    print(f"skills={len(profile.skills)} projects={len(profile.projects)}")


def _projects() -> list[ProjectCreate]:
    """Return evidence-rich projects for deterministic resume matching."""
    return [
        ProjectCreate(
            title="AI Resume Automation / careerOS",
            description=(
                "Built a Python and FastAPI career workflow backend that stores candidate "
                "knowledge, analyzes job descriptions, drafts evidence-backed resumes, "
                "generates PDF documents, and tracks application records."
            ),
            technologies=["Python", "FastAPI", "PostgreSQL", "SQL", "Playwright", "Docker"],
            outcomes=[
                "Generated resume documents from structured candidate evidence.",
                "Tracked application and job records through API-based backend services.",
                "Integrated browser automation for authorized public job-page extraction.",
            ],
            github_url="https://github.com/amina-rahman-dev/careeros",
            start_date=date(2025, 11, 1),
        ),
        ProjectCreate(
            title="Legal Document OCR and Extraction System",
            description=(
                "Created a document-processing service that converts OCR text into validated "
                "structured records and exposes extraction results through FastAPI endpoints."
            ),
            technologies=["Python", "FastAPI", "PostgreSQL", "SQL", "Docker"],
            outcomes=[
                "Extracted structured data from unstructured legal-document text.",
                "Reduced repetitive review work with validation-driven automation.",
                "Built API-based backend services for document records.",
            ],
            github_url="https://github.com/amina-rahman-dev/legal-document-extraction",
            start_date=date(2025, 3, 1),
            end_date=date(2025, 8, 31),
        ),
        ProjectCreate(
            title="AI Workflow Automation System",
            description=(
                "Designed webhook-driven AI workflows for intake, retrieval-augmented "
                "generation, human review, and downstream notifications."
            ),
            technologies=[
                "Python",
                "OpenAI API",
                "LangGraph",
                "LangChain",
                "RAG",
                "Webhooks",
                "n8n",
                "Zapier",
            ],
            outcomes=[
                "Automated repetitive workflows while preserving review checkpoints.",
                "Connected APIs and webhooks across AI-assisted workflow stages.",
                "Used RAG patterns to ground generated responses in retrieved context.",
            ],
            github_url="https://github.com/amina-rahman-dev/ai-workflow-automation",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 10, 31),
        ),
        ProjectCreate(
            title="Web Scraping and Job Data Extraction Tool",
            description=(
                "Developed an authorized public-page extraction tool that uses Playwright "
                "and Selenium to capture visible job content and normalize posting details."
            ),
            technologies=["Python", "Playwright", "Selenium", "APIs", "Docker"],
            outcomes=[
                "Integrated browser automation for repeatable visible-page extraction.",
                "Extracted structured job data from unstructured posting text.",
                "Added validation and warnings for incomplete extraction results.",
            ],
            github_url="https://github.com/amina-rahman-dev/job-data-extractor",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 31),
        ),
    ]


if __name__ == "__main__":
    main()
