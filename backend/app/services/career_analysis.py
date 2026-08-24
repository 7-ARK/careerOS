"""Bounded orchestration for the recruiter-facing golden career-analysis flow."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.observability import log_analysis_stage
from app.features.document_generation import DocumentGenerationService
from app.features.resume_intelligence.grounding import validate_resume_grounding
from app.features.resume_intelligence.matching import EvidenceMatchService
from app.features.resume_intelligence.quality import DeterministicResumeQualityEngine
from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    DeterministicHashEmbeddingProvider,
)
from app.models import CandidateProfile, CareerAnalysisRun, JobAnalysis, ResumeDraft
from app.models.enums import (
    ApplicationStatus,
    CareerAnalysisStage,
    CareerAnalysisStatus,
    DocumentFormat,
    ResumeDraftStatus,
)
from app.repositories import (
    CandidateProfileRepository,
    CareerAnalysisRunRepository,
    GeneratedDocumentRepository,
)
from app.schemas import (
    ApplicationRecordCreate,
    DocumentGenerationRequest,
    GeneratedDocumentRead,
    GoldenCareerAnalysisRead,
    GoldenCareerAnalysisRequest,
    GoldenCareerReviewRequest,
    GroundingValidationResult,
    ManualJobImportRequest,
    MatchExplanation,
    PipelineStageRecord,
    ResumeDraftRead,
    StructuredJobRequirements,
)
from app.services.application_tracker import ApplicationTrackerService
from app.services.exceptions import (
    CareerAnalysisExecutionError,
    CareerAnalysisRunNotFoundError,
    InvalidCareerAnalysisStateError,
    ProfileNotFoundError,
    ResumeGroundingError,
)
from app.services.job_import import ManualJobImportService
from app.services.resume_intelligence import ResumeIntelligenceService


class GoldenCareerAnalysisService:
    """Execute one inspectable flow while delegating to existing domain services."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.runs = CareerAnalysisRunRepository(session)
        self.profiles = CandidateProfileRepository(session)
        self.documents = GeneratedDocumentRepository(session)
        self.applications = ApplicationTrackerService(session)
        self.document_generation = DocumentGenerationService(session)

    def start(
        self,
        request: GoldenCareerAnalysisRequest,
        *,
        user_id: UUID,
    ) -> GoldenCareerAnalysisRead:
        """Run analysis through draft validation and stop at explicit human review."""
        started_at = datetime.now(UTC)
        run = self.runs.create(
            user_id=user_id,
            candidate_profile_id=request.candidate_profile_id,
            status=str(CareerAnalysisStatus.RUNNING),
            current_stage=str(CareerAnalysisStage.PROFILE_VALIDATION),
            provider="deterministic_local" if request.mode == "mock" else "configured",
            token_usage={},
            estimated_cost_usd=Decimal("0"),
            started_at=started_at,
            structured_requirements={},
            evidence_matches={},
            stage_results=[],
        )
        self._commit()

        candidate = self._execute_stage(
            run,
            CareerAnalysisStage.PROFILE_VALIDATION,
            lambda: self._require_owned_candidate(request.candidate_profile_id, user_id),
            summary="Validated the authenticated candidate profile and durable evidence source.",
        )
        importer = ManualJobImportService(self.session)
        imported = self._execute_stage(
            run,
            CareerAnalysisStage.JOB_IMPORT,
            lambda: importer.import_job_posting(
                ManualJobImportRequest(
                    candidate_profile_id=request.candidate_profile_id,
                    raw_title=request.raw_title,
                    company_name=request.company_name,
                    location=request.location,
                    source_platform=request.source_platform,
                    job_url=request.job_url,
                    description_text=request.description_text,
                    employment_type=request.employment_type,
                    create_application_record=False,
                )
            ),
            summary="Saved the original manual job description and its validated analysis.",
        )
        run.job_description_id = imported.job_description.id
        run.job_analysis_id = imported.analysis.id
        self._commit()

        matching, resume_intelligence = self._services_for_mode(request.mode)
        job_model = self.session.get(JobAnalysis, imported.analysis.id)
        if job_model is None:
            raise InvalidCareerAnalysisStateError("persisted job analysis could not be reloaded")
        job_source = job_model.job_description
        requirements = self._execute_stage(
            run,
            CareerAnalysisStage.REQUIREMENT_EXTRACTION,
            lambda: matching.structured_requirements(job_source, job_model),
            summary="Projected the typed job analysis into scored and context-only requirements.",
        )
        run.structured_requirements = requirements.model_dump(mode="json")
        self._commit()

        evidence_count = self._execute_stage(
            run,
            CareerAnalysisStage.EVIDENCE_RETRIEVAL,
            lambda: len(matching.retriever.collect(candidate)),
            summary="Indexed verified candidate chunks with stable evidence IDs.",
        )
        explanation = self._execute_stage(
            run,
            CareerAnalysisStage.MATCH_ANALYSIS,
            lambda: matching.explain(
                candidate.id,
                imported.job_description.id,
                top_k=request.top_k,
            ),
            summary=(
                f"Mapped {len(requirements.requirements)} requirements across "
                f"{evidence_count} verified evidence chunks."
            ),
        )
        run.evidence_matches = {"match_explanation": explanation.model_dump(mode="json")}
        run.evidence_coverage_score = explanation.evidence_coverage.score
        run.provider = explanation.retrieval_provider
        run.model_name = explanation.embedding_model
        self._commit()

        resume_result, draft = self._execute_stage(
            run,
            CareerAnalysisStage.RESUME_DRAFT,
            lambda: self._create_analysis_and_draft(
                resume_intelligence,
                candidate.id,
                imported.analysis.id,
            ),
            summary="Created a reviewable draft from candidate-owned facts without approving it.",
        )
        run.resume_analysis_id = resume_result.analysis.id
        run.resume_draft_id = draft.id
        self._commit()

        draft_model = self.session.get(ResumeDraft, draft.id)
        if draft_model is None:
            raise InvalidCareerAnalysisStateError("persisted resume draft could not be reloaded")
        grounding = self._execute_stage(
            run,
            CareerAnalysisStage.GROUNDING_VALIDATION,
            lambda: self._validated_grounding(
                candidate, draft_model, retriever=matching.retriever
            ),
            summary="Validated every draft claim group against stable verified evidence IDs.",
        )
        run.evidence_matches = {
            **run.evidence_matches,
            "grounding_validation": grounding.model_dump(mode="json"),
        }
        run.status = str(CareerAnalysisStatus.AWAITING_REVIEW)
        run.current_stage = str(CareerAnalysisStage.HUMAN_REVIEW)
        self._append_stage(
            run,
            PipelineStageRecord(
                stage=CareerAnalysisStage.HUMAN_REVIEW,
                status="awaiting_review",
                started_at=datetime.now(UTC),
                provider="human",
                summary="Draft is waiting for an explicit approve or reject decision.",
            ),
        )
        self._commit()
        return self._read(run)

    def review(
        self,
        run_id: UUID,
        request: GoldenCareerReviewRequest,
        *,
        user_id: UUID,
    ) -> GoldenCareerAnalysisRead:
        """Record a human decision and export only an explicitly approved draft."""
        run = self._require_run(run_id, user_id)
        if run.status != CareerAnalysisStatus.AWAITING_REVIEW:
            raise InvalidCareerAnalysisStateError(
                "career analysis must be awaiting_review before a review decision"
            )
        if run.resume_draft_id is None:
            raise InvalidCareerAnalysisStateError("career analysis has no resume draft to review")
        draft = self.session.get(ResumeDraft, run.resume_draft_id)
        candidate = self._require_owned_candidate(run.candidate_profile_id, user_id)
        if draft is None:
            raise InvalidCareerAnalysisStateError("career analysis resume draft was not found")
        grounding = validate_resume_grounding(candidate, draft)
        if not grounding.valid:
            raise ResumeGroundingError(
                "resume draft cannot be approved because grounding validation failed"
            )
        self._complete_waiting_review_stage(run, request.decision)
        run.review_notes = request.review_notes
        if request.decision == "reject":
            ResumeIntelligenceService(self.session).update_resume_draft_status(
                draft.id,
                ResumeDraftStatus.REJECTED,
            )
            run.status = str(CareerAnalysisStatus.REJECTED)
            run.finished_at = datetime.now(UTC)
            self._commit()
            return self._read(run)

        ResumeIntelligenceService(self.session).update_resume_draft_status(
            draft.id,
            ResumeDraftStatus.APPROVED,
        )
        generated = self._execute_stage(
            run,
            CareerAnalysisStage.DOCUMENT_EXPORT,
            lambda: [
                self.document_generation.generate_from_resume_draft(
                    DocumentGenerationRequest(
                        resume_draft_id=draft.id,
                        template_name=request.resume_template_name,
                        output_format=output_format,
                    )
                ).document
                for output_format in request.export_formats
            ],
            summary="Generated approved local DOCX/PDF artifacts requested by the reviewer.",
        )
        preferred = next(
            (
                document
                for document in generated
                if document.output_format == DocumentFormat.PDF
            ),
            generated[0],
        )
        job_analysis = self.session.get(JobAnalysis, draft.job_analysis_id)
        if job_analysis is None or job_analysis.job_description is None:
            raise InvalidCareerAnalysisStateError(
                "career analysis job source was not available for application tracking"
            )
        job_source = job_analysis.job_description
        application = self._execute_stage(
            run,
            CareerAnalysisStage.APPLICATION_TRACKING,
            lambda: self.applications.create_application_record(
                ApplicationRecordCreate(
                    candidate_profile_id=candidate.id,
                    job_description_id=job_source.id,
                    job_analysis_id=job_analysis.id,
                    generated_document_id=preferred.id,
                    company_name=job_source.company_name or "Unknown company",
                    role_title=job_source.raw_title,
                    job_url=job_source.job_url,
                    status=ApplicationStatus.SAVED,
                    evidence_coverage_score=run.evidence_coverage_score,
                )
            ),
            summary=(
                "Saved the reviewed application with its calculated Evidence Coverage Score "
                "and approved resume."
            ),
        )
        run.application_record_id = application.id
        run.status = str(CareerAnalysisStatus.COMPLETED)
        run.finished_at = datetime.now(UTC)
        self._commit()
        return self._read(run)

    def get(self, run_id: UUID, *, user_id: UUID) -> GoldenCareerAnalysisRead:
        return self._read(self._require_run(run_id, user_id))

    def list_for_candidate(
        self,
        candidate_profile_id: UUID,
        *,
        user_id: UUID,
    ) -> list[GoldenCareerAnalysisRead]:
        self._require_owned_candidate(candidate_profile_id, user_id)
        return [
            self._read(run)
            for run in self.runs.list_for_candidate(candidate_profile_id, user_id)
        ]

    def _services_for_mode(
        self,
        mode: str,
    ) -> tuple[EvidenceMatchService, ResumeIntelligenceService]:
        if mode == "mock":
            retriever = CandidateEvidenceRetriever(DeterministicHashEmbeddingProvider())
            return (
                EvidenceMatchService(self.session, retriever=retriever),
                ResumeIntelligenceService(
                    self.session,
                    quality_engine=DeterministicResumeQualityEngine(),
                ),
            )
        return EvidenceMatchService(self.session), ResumeIntelligenceService(self.session)

    @staticmethod
    def _create_analysis_and_draft(
        service: ResumeIntelligenceService,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> tuple[Any, ResumeDraftRead]:
        analysis = service.analyze_candidate_for_job(candidate_profile_id, job_analysis_id)
        return analysis, service.create_resume_draft_from_analysis(analysis.analysis.id)

    def _execute_stage(
        self,
        run: CareerAnalysisRun,
        stage: CareerAnalysisStage,
        operation: Callable[[], Any],
        *,
        summary: str,
    ) -> Any:
        started_at = datetime.now(UTC)
        run.status = str(CareerAnalysisStatus.RUNNING)
        run.current_stage = str(stage)
        self._commit()
        run_id = run.id
        try:
            result = operation()
        except Exception as exc:
            self.session.rollback()
            persisted_run = self.runs.get(run_id)
            if persisted_run is None:
                raise
            run = persisted_run
            finished_at = datetime.now(UTC)
            latency_ms = self._latency_ms(started_at, finished_at)
            self._append_stage(
                run,
                PipelineStageRecord(
                    stage=stage,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    latency_ms=latency_ms,
                    provider=run.provider,
                    model=run.model_name,
                    error=f"{type(exc).__name__}: {str(exc)[:400]}",
                    summary=summary,
                ),
            )
            run.status = str(CareerAnalysisStatus.FAILED)
            run.finished_at = finished_at
            run.error_details = {
                "stage": str(stage),
                "error_type": type(exc).__name__,
                "message": str(exc)[:400],
            }
            self._commit()
            log_analysis_stage(
                run_id=run.id,
                stage=stage,
                status="failed",
                provider=run.provider,
                model=run.model_name,
                latency_ms=latency_ms,
                estimated_cost_usd=run.estimated_cost_usd,
                error_type=type(exc).__name__,
            )
            raise CareerAnalysisExecutionError(stage, run.id) from exc
        finished_at = datetime.now(UTC)
        latency_ms = self._latency_ms(started_at, finished_at)
        self._append_stage(
            run,
            PipelineStageRecord(
                stage=stage,
                status="completed",
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
                provider=run.provider,
                model=run.model_name,
                summary=summary,
            ),
        )
        self._commit()
        log_analysis_stage(
            run_id=run.id,
            stage=stage,
            status="completed",
            provider=run.provider,
            model=run.model_name,
            latency_ms=latency_ms,
            estimated_cost_usd=run.estimated_cost_usd,
        )
        return result

    def _complete_waiting_review_stage(self, run: CareerAnalysisRun, decision: str) -> None:
        stages = list(run.stage_results)
        for index in range(len(stages) - 1, -1, -1):
            if stages[index].get("stage") == CareerAnalysisStage.HUMAN_REVIEW:
                started_at = datetime.fromisoformat(str(stages[index]["started_at"]))
                finished_at = datetime.now(UTC)
                stages[index] = PipelineStageRecord(
                    stage=CareerAnalysisStage.HUMAN_REVIEW,
                    status="completed",
                    started_at=started_at,
                    finished_at=finished_at,
                    latency_ms=self._latency_ms(started_at, finished_at),
                    provider="human",
                    summary=f"Human reviewer selected {decision}.",
                ).model_dump(mode="json")
                run.stage_results = stages
                return

    def _read(self, run: CareerAnalysisRun) -> GoldenCareerAnalysisRead:
        requirements = (
            StructuredJobRequirements.model_validate(run.structured_requirements)
            if run.structured_requirements
            else None
        )
        match_payload = run.evidence_matches.get("match_explanation")
        grounding_payload = run.evidence_matches.get("grounding_validation")
        draft = (
            ResumeDraftRead.model_validate(self.session.get(ResumeDraft, run.resume_draft_id))
            if run.resume_draft_id
            else None
        )
        application = (
            self.applications.get_application_record(run.application_record_id)
            if run.application_record_id
            else None
        )
        documents = (
            [
                GeneratedDocumentRead.model_validate(document)
                for document in self.documents.list_by_draft(run.resume_draft_id)
            ]
            if run.resume_draft_id
            else []
        )
        return GoldenCareerAnalysisRead(
            id=run.id,
            user_id=run.user_id,
            candidate_profile_id=run.candidate_profile_id,
            job_description_id=run.job_description_id,
            job_analysis_id=run.job_analysis_id,
            resume_analysis_id=run.resume_analysis_id,
            resume_draft_id=run.resume_draft_id,
            application_record_id=run.application_record_id,
            status=run.status,
            current_stage=run.current_stage,
            provider=run.provider,
            model_name=run.model_name,
            token_usage=run.token_usage,
            estimated_cost_usd=run.estimated_cost_usd,
            started_at=run.started_at,
            finished_at=run.finished_at,
            structured_requirements=requirements,
            match_explanation=(
                MatchExplanation.model_validate(match_payload) if match_payload else None
            ),
            evidence_coverage_score=run.evidence_coverage_score,
            stages=[PipelineStageRecord.model_validate(item) for item in run.stage_results],
            error_details=run.error_details,
            review_notes=run.review_notes,
            resume_draft=draft,
            application_record=application,
            generated_documents=documents,
            grounding_validation=(
                GroundingValidationResult.model_validate(grounding_payload)
                if grounding_payload
                else None
            ),
        )

    def _require_run(self, run_id: UUID, user_id: UUID) -> CareerAnalysisRun:
        run = self.runs.get_for_user(run_id, user_id)
        if run is None:
            raise CareerAnalysisRunNotFoundError(
                f"career analysis run {run_id} was not found"
            )
        return run

    def _require_owned_candidate(
        self,
        candidate_profile_id: UUID,
        user_id: UUID,
    ) -> CandidateProfile:
        candidate = self.profiles.get_complete_for_user(candidate_profile_id, user_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate

    @staticmethod
    def _validated_grounding(
        candidate: CandidateProfile,
        draft: ResumeDraft,
        *,
        retriever: CandidateEvidenceRetriever,
    ) -> GroundingValidationResult:
        result = validate_resume_grounding(candidate, draft, retriever=retriever)
        if not result.valid:
            raise ResumeGroundingError(
                "resume draft contains unsupported claims: "
                + "; ".join(result.unsupported_claims[:3])
            )
        return result

    @staticmethod
    def _append_stage(run: CareerAnalysisRun, stage: PipelineStageRecord) -> None:
        run.stage_results = [*run.stage_results, stage.model_dump(mode="json")]

    @staticmethod
    def _latency_ms(started_at: datetime, finished_at: datetime) -> int:
        return max(0, int((finished_at - started_at).total_seconds() * 1000))

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
