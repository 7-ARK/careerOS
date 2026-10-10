"""Recruiter-facing golden flow and evidence-grounded match endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    CurrentUser,
    get_application_tracker_service,
    get_evidence_match_service,
    get_golden_career_analysis_service,
    get_knowledge_base_service,
)
from app.core.config import Settings
from app.features.resume_intelligence.matching import EvidenceMatchService
from app.schemas import (
    GoldenCareerAnalysisRead,
    GoldenCareerAnalysisRequest,
    GoldenCareerReviewRequest,
    MatchExplainRequest,
    MatchExplanation,
)
from app.services import (
    ApplicationTrackerService,
    KnowledgeBaseService,
)
from app.services.career_analysis import GoldenCareerAnalysisService

router = APIRouter(prefix="/api/v1/career-analyses", tags=["career-analysis"])
jobs_router = APIRouter(prefix="/api/v1/jobs", tags=["career-analysis"])
GoldenService = Annotated[
    GoldenCareerAnalysisService,
    Depends(get_golden_career_analysis_service),
]
MatchService = Annotated[EvidenceMatchService, Depends(get_evidence_match_service)]
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]
TrackerService = Annotated[
    ApplicationTrackerService,
    Depends(get_application_tracker_service),
]


@router.post("", response_model=GoldenCareerAnalysisRead, status_code=status.HTTP_201_CREATED)
def start_golden_career_analysis(
    request: GoldenCareerAnalysisRequest,
    service: GoldenService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> GoldenCareerAnalysisRead:
    """Run the deterministic manual-input flow and stop before human approval."""
    _reject_external_preview_live_mode(request.mode)
    candidates.get_profile(request.candidate_profile_id, user_id=current_user.id)
    return service.start(request, user_id=current_user.id)


@router.get("/candidate/{candidate_profile_id}", response_model=list[GoldenCareerAnalysisRead])
def list_candidate_career_analyses(
    candidate_profile_id: UUID,
    service: GoldenService,
    current_user: CurrentUser,
) -> list[GoldenCareerAnalysisRead]:
    """List durable golden-flow runs for one owned candidate profile."""
    return service.list_for_candidate(candidate_profile_id, user_id=current_user.id)


@router.get("/{run_id}", response_model=GoldenCareerAnalysisRead)
def get_golden_career_analysis(
    run_id: UUID,
    service: GoldenService,
    current_user: CurrentUser,
) -> GoldenCareerAnalysisRead:
    """Return one authenticated user's inspectable analysis run."""
    return service.get(run_id, user_id=current_user.id)


@router.post("/{run_id}/review", response_model=GoldenCareerAnalysisRead)
def review_golden_career_analysis(
    run_id: UUID,
    request: GoldenCareerReviewRequest,
    service: GoldenService,
    current_user: CurrentUser,
) -> GoldenCareerAnalysisRead:
    """Approve or reject a grounded draft; only approval can export documents."""
    return service.review(run_id, request, user_id=current_user.id)


@jobs_router.post("/{job_id}/match-explain", response_model=MatchExplanation)
def explain_candidate_job_match(
    job_id: UUID,
    request: MatchExplainRequest,
    service: MatchService,
    candidates: CandidateService,
    tracker: TrackerService,
    current_user: CurrentUser,
) -> MatchExplanation:
    """Explain a saved candidate/job relationship with stable evidence citations."""
    candidates.get_profile(request.candidate_profile_id, user_id=current_user.id)
    if not tracker.candidate_has_job_record(request.candidate_profile_id, job_id):
        raise HTTPException(
            status_code=404,
            detail="saved job was not found for the selected candidate",
        )
    return service.explain(request.candidate_profile_id, job_id, top_k=request.top_k)


def _reject_external_preview_live_mode(mode: str) -> None:
    if Settings.from_env().preview_mode and mode != "mock":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="live analysis is disabled in external preview mode",
        )
