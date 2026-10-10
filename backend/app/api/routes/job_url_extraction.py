"""Playwright URL extraction pipeline API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    CurrentUser,
    get_job_url_pipeline_service,
    get_knowledge_base_service,
)
from app.core.config import Settings
from app.schemas import (
    JobUrlExtractionRequest,
    JobUrlExtractionResult,
    JobUrlPipelineRequest,
    JobUrlPipelineResult,
)
from app.services import JobUrlPipelineService, KnowledgeBaseService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])
UrlPipelineService = Annotated[
    JobUrlPipelineService,
    Depends(get_job_url_pipeline_service),
]
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


@router.post("/extract", response_model=JobUrlExtractionResult)
def extract_job_url(
    request: JobUrlExtractionRequest,
    service: UrlPipelineService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> JobUrlExtractionResult:
    """Extract editable job fields without starting resume generation."""
    _reject_external_preview_extraction()
    candidates.get_profile(request.candidate_profile_id, user_id=current_user.id)
    return service.extract_url(request)


@router.post("/url", response_model=JobUrlPipelineResult)
def run_url_pipeline(
    request: JobUrlPipelineRequest,
    service: UrlPipelineService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> JobUrlPipelineResult:
    """Extract one authorized URL and run the pipeline when ready."""
    _reject_external_preview_extraction()
    candidates.get_profile(request.candidate_profile_id, user_id=current_user.id)
    return service.run_url_pipeline(request)


def _reject_external_preview_extraction() -> None:
    if Settings.from_env().preview_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="job URL extraction is disabled in external preview mode",
        )
