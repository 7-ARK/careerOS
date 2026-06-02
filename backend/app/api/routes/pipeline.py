"""Manual end-to-end pipeline API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_application_pipeline_service
from app.schemas import ManualJobPipelineRequest, ManualJobPipelineResult
from app.services import ApplicationPipelineService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])
PipelineService = Annotated[
    ApplicationPipelineService,
    Depends(get_application_pipeline_service),
]


@router.post("/manual", response_model=ManualJobPipelineResult)
def run_manual_pipeline(
    request: ManualJobPipelineRequest,
    service: PipelineService,
) -> ManualJobPipelineResult:
    """Run the existing manual job application pipeline."""
    return service.run_manual_job_pipeline(request)
