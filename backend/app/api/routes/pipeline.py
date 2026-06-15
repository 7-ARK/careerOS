"""Manual end-to-end pipeline API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    CurrentUser,
    get_application_pipeline_service,
    get_knowledge_base_service,
)
from app.schemas import ManualJobPipelineRequest, ManualJobPipelineResult
from app.services import ApplicationPipelineService, KnowledgeBaseService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])
PipelineService = Annotated[
    ApplicationPipelineService,
    Depends(get_application_pipeline_service),
]
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


@router.post("/manual", response_model=ManualJobPipelineResult)
def run_manual_pipeline(
    request: ManualJobPipelineRequest,
    service: PipelineService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> ManualJobPipelineResult:
    """Run the existing manual job application pipeline."""
    candidates.get_profile(request.candidate_profile_id, user_id=current_user.id)
    return service.run_manual_job_pipeline(request)
