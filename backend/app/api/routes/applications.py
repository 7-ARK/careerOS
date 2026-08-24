"""Lightweight application-record API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    CurrentUser,
    get_application_tracker_service,
    get_knowledge_base_service,
)
from app.core.config import Settings
from app.schemas import ApplicationRecordRead, ApplicationStatusUpdate
from app.services import ApplicationTrackerService, KnowledgeBaseService

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
TrackerService = Annotated[
    ApplicationTrackerService,
    Depends(get_application_tracker_service),
]
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


@router.get("/{candidate_profile_id}", response_model=list[ApplicationRecordRead])
def list_candidate_applications(
    candidate_profile_id: UUID,
    service: TrackerService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> list[ApplicationRecordRead]:
    """List one candidate's lightweight application records."""
    candidates.get_profile(candidate_profile_id, user_id=current_user.id)
    return service.list_candidate_applications(candidate_profile_id)


@router.patch("/{application_id}/applied", response_model=ApplicationRecordRead)
def mark_application_applied(
    application_id: UUID,
    service: TrackerService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> ApplicationRecordRead:
    """Mark one lightweight application record as applied."""
    _reject_external_preview_application_mutation()
    record = service.get_application_record(application_id)
    candidates.get_profile(record.candidate_profile_id, user_id=current_user.id)
    return service.mark_as_applied(application_id)


@router.patch("/{application_id}/not-applied", response_model=ApplicationRecordRead)
def mark_application_not_applied(
    application_id: UUID,
    service: TrackerService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> ApplicationRecordRead:
    """Return one lightweight application record to not-applied."""
    _reject_external_preview_application_mutation()
    record = service.get_application_record(application_id)
    candidates.get_profile(record.candidate_profile_id, user_id=current_user.id)
    return service.mark_as_not_applied(application_id)


@router.patch("/{application_id}/status", response_model=ApplicationRecordRead)
def update_application_status(
    application_id: UUID,
    request: ApplicationStatusUpdate,
    service: TrackerService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> ApplicationRecordRead:
    """Update one owned record across the supported application lifecycle."""
    _reject_external_preview_application_mutation()
    record = service.get_application_record(application_id)
    candidates.get_profile(record.candidate_profile_id, user_id=current_user.id)
    return service.update_status(application_id, request.status)


def _reject_external_preview_application_mutation() -> None:
    """Keep the shared recruiter-preview tracker read-only."""
    if Settings.from_env().preview_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application status updates are disabled in the shared preview.",
        )
