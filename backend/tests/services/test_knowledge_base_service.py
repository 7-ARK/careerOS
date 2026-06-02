"""Service tests for candidate knowledge-base workflows."""

import unittest
from datetime import date
from decimal import Decimal

from app.models import ApplicationStatus, RemotePreference
from app.schemas import (
    ApplicationHistoryCreate,
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CareerGoalCreate,
    ProjectCreate,
    ResumeVersionCreate,
    SkillCreate,
    WorkExperienceCreate,
)
from app.services import DuplicateSkillError, InvalidResumeVersionError, KnowledgeBaseService
from tests.support import create_test_engine, create_test_session


class KnowledgeBaseServiceTests(unittest.TestCase):
    """Verify transactional service operations and ownership rules."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.service = KnowledgeBaseService(self.session)
        self.profile = self.service.create_candidate_profile(
            CandidateProfileCreate(full_name="Grace Hopper", email="grace@example.com")
        )

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_build_complete_candidate_profile(self) -> None:
        self.service.update_profile(
            self.profile.id,
            CandidateProfileUpdate(headline="Compiler Pioneer"),
        )
        self.service.add_experience(
            self.profile.id,
            WorkExperienceCreate(
                company="US Navy",
                job_title="Rear Admiral",
                start_date=date(1943, 1, 1),
                achievements=["Popularized machine-independent programming languages"],
            ),
        )
        self.service.add_project(
            self.profile.id,
            ProjectCreate(
                title="COBOL",
                description="Advanced a portable business programming language",
                technologies=["Compiler Design"],
                outcomes=["Improved software portability"],
            ),
        )
        self.service.add_skill(
            self.profile.id,
            SkillCreate(
                name="Compiler Design",
                category="Computer Science",
                self_rating=5,
                years_of_experience=Decimal("10.0"),
            ),
        )
        self.service.update_career_goals(
            self.profile.id,
            CareerGoalCreate(
                target_roles=["Principal Engineer"],
                preferred_industries=["Technology"],
                remote_preference=RemotePreference.FLEXIBLE,
            ),
        )

        profile = self.service.get_profile(self.profile.id)

        self.assertEqual(profile.headline, "Compiler Pioneer")
        self.assertEqual(profile.projects[0].title, "COBOL")
        self.assertEqual(profile.skills[0].name, "Compiler Design")
        self.assertEqual(profile.career_goals.target_roles, ["Principal Engineer"])

    def test_add_skill_rejects_duplicate_name(self) -> None:
        skill = SkillCreate(
            name="Python",
            category="Programming",
            self_rating=5,
            years_of_experience=Decimal("4.0"),
        )
        self.service.add_skill(self.profile.id, skill)

        with self.assertRaises(DuplicateSkillError):
            self.service.add_skill(self.profile.id, skill)

    def test_record_application_links_owned_resume_version(self) -> None:
        resume = self.service.create_resume_version(
            self.profile.id,
            ResumeVersionCreate(title="Backend Resume", content={"summary": "Engineer"}),
        )

        application = self.service.record_application(
            self.profile.id,
            ApplicationHistoryCreate(
                resume_version_id=resume.id,
                company="Example Corp",
                job_title="Principal Engineer",
                application_date=date(2026, 5, 31),
                status=ApplicationStatus.APPLIED,
            ),
        )

        self.assertEqual(application.resume_version_id, resume.id)

    def test_record_application_rejects_another_profiles_resume(self) -> None:
        other_profile = self.service.create_candidate_profile(
            CandidateProfileCreate(full_name="Other Candidate")
        )
        resume = self.service.create_resume_version(
            other_profile.id,
            ResumeVersionCreate(title="Other Resume"),
        )

        with self.assertRaises(InvalidResumeVersionError):
            self.service.record_application(
                self.profile.id,
                ApplicationHistoryCreate(
                    resume_version_id=resume.id,
                    company="Example Corp",
                    job_title="Engineer",
                    application_date=date(2026, 5, 31),
                ),
            )
