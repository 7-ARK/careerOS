"""Repository tests for generated-document metadata."""

import unittest
from decimal import Decimal

from app.models import CandidateProfile, JobAnalysis, JobDescription, ResumeAnalysis, ResumeDraft
from app.models.enums import (
    DocumentFormat,
    DocumentGenerationStatus,
    ResumeDraftStatus,
    ResumeTemplateName,
    SeniorityLevel,
)
from app.repositories import GeneratedDocumentRepository
from tests.support import create_test_engine, create_test_session


class GeneratedDocumentRepositoryTests(unittest.TestCase):
    """Exercise generated-document persistence and scoped listing."""

    def setUp(self) -> None:
        self.engine = create_test_engine()
        self.session = create_test_session(self.engine)
        self.documents = GeneratedDocumentRepository(self.session)
        self.profile = CandidateProfile(full_name="Ada Lovelace")
        description = JobDescription(raw_title="Backend Engineer", description_text="Build APIs.")
        self.job_analysis = JobAnalysis(
            job_description=description,
            revision=1,
            analyzer_name="rule_based",
            analyzer_version="test",
            normalized_title="Backend Engineer",
            seniority_level=SeniorityLevel.MID_LEVEL,
            job_summary="Backend role.",
        )
        analysis = ResumeAnalysis(
            candidate_profile=self.profile,
            job_analysis=self.job_analysis,
            overall_match_score=Decimal("75"),
            keyword_match_score=Decimal("75"),
            skills_match_score=Decimal("75"),
            technology_match_score=Decimal("75"),
            experience_match_score=Decimal("75"),
            project_match_score=Decimal("75"),
            education_match_score=Decimal("50"),
            suggested_resume_summary="Backend engineer.",
        )
        self.draft = ResumeDraft(
            resume_analysis=analysis,
            candidate_profile=self.profile,
            job_analysis=self.job_analysis,
            title="Backend Engineer Resume",
            target_role="Backend Engineer",
            summary="Backend engineer.",
            status=ResumeDraftStatus.APPROVED,
        )
        self.session.add(self.draft)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_and_lists_generated_document_metadata(self) -> None:
        document = self.documents.create_generated_document(
            resume_draft_id=self.draft.id,
            candidate_profile_id=self.profile.id,
            job_analysis_id=self.job_analysis.id,
            template_name=ResumeTemplateName.CLEAN_ATS,
            output_format=DocumentFormat.MARKDOWN,
            file_name="resume.md",
            file_path="generated/resumes/resume.md",
            file_size_bytes=12,
            checksum="a" * 64,
            generation_status=DocumentGenerationStatus.COMPLETED,
        )
        self.session.commit()

        self.assertEqual(self.documents.get(document.id).id, document.id)
        self.assertEqual(self.documents.list_by_candidate(self.profile.id), [document])
        self.assertEqual(self.documents.list_by_draft(self.draft.id), [document])


if __name__ == "__main__":
    unittest.main()
