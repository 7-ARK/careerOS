"""Lightweight application-record API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_application_tracker_service
from app.schemas import ApplicationRecordRead
from app.services import ApplicationTrackerService

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
TrackerService = Annotated[
    ApplicationTrackerService,
    Depends(get_application_tracker_service),
]


@router.get("/{candidate_profile_id}", response_model=list[ApplicationRecordRead])
def list_candidate_applications(
    candidate_profile_id: UUID,
    service: TrackerService,
) -> list[ApplicationRecordRead]:
    """List one candidate's lightweight application records."""
    return service.list_candidate_applications(candidate_profile_id)


@router.patch("/{application_id}/applied", response_model=ApplicationRecordRead)
def mark_application_applied(
    application_id: UUID,
    service: TrackerService,
) -> ApplicationRecordRead:
    """Mark one lightweight application record as applied."""
    return service.mark_as_applied(application_id)


@router.patch("/{application_id}/not-applied", response_model=ApplicationRecordRead)
def mark_application_not_applied(
    application_id: UUID,
    service: TrackerService,
) -> ApplicationRecordRead:
    """Return one lightweight application record to not-applied."""
    return service.mark_as_not_applied(application_id)
