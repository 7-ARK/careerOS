"""Playwright URL extraction pipeline API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_job_url_pipeline_service
from app.schemas import JobUrlPipelineRequest, JobUrlPipelineResult
from app.services import JobUrlPipelineService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])
UrlPipelineService = Annotated[
    JobUrlPipelineService,
    Depends(get_job_url_pipeline_service),
]


@router.post("/url", response_model=JobUrlPipelineResult)
def run_url_pipeline(
    request: JobUrlPipelineRequest,
    service: UrlPipelineService,
) -> JobUrlPipelineResult:
    """Extract one authorized URL and run the pipeline when ready."""
    return service.run_url_pipeline(request)
