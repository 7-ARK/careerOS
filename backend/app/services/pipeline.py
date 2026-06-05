"""Thin orchestration for the manual end-to-end application pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.enums import (
    PipelineStage,
    PipelineStatus,
    ResumeDraftStatus,
)
from app.schemas import (
    DocumentGenerationRequest,
    ManualJobImportRequest,
    ManualJobPipelineRequest,
    ManualJobPipelineResult,
)
from app.services.application_tracker import ApplicationTrackerService
from app.services.exceptions import PipelineExecutionError
from app.services.job_import import ManualJobImportService
from app.services.resume_intelligence import ResumeIntelligenceService

if TYPE_CHECKING:
    from app.features.document_generation import DocumentGenerationService


class ApplicationPipelineService:
    """Connect existing services into one local manual job-application workflow."""

    def __init__(
        self,
        session: Session,
        *,
        importer: ManualJobImportService | None = None,
        resume_intelligence: ResumeIntelligenceService | None = None,
        document_generation: DocumentGenerationService | None = None,
        applications: ApplicationTrackerService | None = None,
    ) -> None:
        """Build an injectable pipeline from the existing domain services."""
        self.importer = importer or ManualJobImportService(session)
        self.resume_intelligence = resume_intelligence or ResumeIntelligenceService(session)
        if document_generation is None:
            from app.features.document_generation import DocumentGenerationService

            document_generation = DocumentGenerationService(session)
        self.document_generation = document_generation
        self.applications = applications or ApplicationTrackerService(session)

    def run_manual_job_pipeline(self, request: ManualJobPipelineRequest) -> ManualJobPipelineResult:
        """Run the deterministic local workflow without duplicating domain logic."""
        imported = self._run(
            PipelineStage.JOB_IMPORT,
            lambda: self.importer.import_job_posting(
                ManualJobImportRequest(
                    **request.model_dump(exclude={"resume_template_name", "document_format"})
                )
            ),
        )
        resume_analysis = self._run(
            PipelineStage.RESUME_ANALYSIS,
            lambda: self.resume_intelligence.analyze_candidate_for_job(
                request.candidate_profile_id,
                imported.analysis.id,
            ),
        )
        draft = self._run(
            PipelineStage.RESUME_DRAFT,
            lambda: self.resume_intelligence.create_resume_draft_from_analysis(
                resume_analysis.analysis.id
            ),
        )
        draft = self._run(
            PipelineStage.RESUME_DRAFT_APPROVAL,
            lambda: self.resume_intelligence.update_resume_draft_status(
                draft.id,
                ResumeDraftStatus.APPROVED,
            ),
        )
        generated = self._run(
            PipelineStage.DOCUMENT_GENERATION,
            lambda: self.document_generation.generate_from_resume_draft(
                DocumentGenerationRequest(
                    resume_draft_id=draft.id,
                    template_name=request.resume_template_name,
                    output_format=request.document_format,
                )
            ),
        )
        application_record = imported.application_record
        if application_record is not None:
            application_record = self._run(
                PipelineStage.APPLICATION_RECORD_UPDATE,
                lambda: self.applications.attach_resume_document(
                    application_record.id,
                    generated.document.id,
                ),
            )
        project_review = self.resume_intelligence.get_project_selection_review(
            request.candidate_profile_id,
            imported.analysis.id,
            draft.id,
        )
        return ManualJobPipelineResult(
            job_description_id=imported.job_description.id,
            job_analysis_id=imported.analysis.id,
            resume_analysis_id=resume_analysis.analysis.id,
            resume_draft_id=draft.id,
            generated_document_id=generated.document.id,
            generated_file_path=generated.document.file_path,
            application_record_id=application_record.id if application_record else None,
            company_name=request.company_name,
            role_title=request.raw_title,
            match_score=resume_analysis.analysis.overall_match_score,
            document_format=request.document_format,
            template_name=request.resume_template_name,
            status=PipelineStatus.COMPLETED,
            matched_skills=resume_analysis.analysis.matched_skills,
            missing_skills=resume_analysis.analysis.missing_skills,
            matched_technologies=resume_analysis.analysis.matched_technologies,
            missing_technologies=resume_analysis.analysis.missing_technologies,
            selected_projects=project_review["selected_projects"],
            excluded_projects=project_review["excluded_projects"],
            warnings=draft.truthfulness_notes,
            next_actions=self._next_actions(application_record is not None),
        )

    @staticmethod
    def _run[ResultT](stage: PipelineStage, operation: Callable[[], ResultT]) -> ResultT:
        """Wrap one delegated service call with clear stage-level failure context."""
        try:
            return operation()
        except PipelineExecutionError:
            raise
        except Exception as exc:
            raise PipelineExecutionError(stage, str(exc)) from exc

    @staticmethod
    def _next_actions(has_application_record: bool) -> list[str]:
        """Return concise next actions without introducing workflow automation."""
        actions = ["Review the generated resume document."]
        if has_application_record:
            actions.append("Submit the application and mark the record as applied.")
        else:
            actions.append("Create an application record when you are ready to apply.")
        return actions
