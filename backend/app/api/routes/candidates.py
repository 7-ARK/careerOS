"""Candidate profile management API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import CurrentUser, get_knowledge_base_service
from app.schemas import (
    CandidateProfileDetailsCreate,
    CandidateProfileDetailsUpdate,
    CandidateProfileRead,
    CandidateProfileSummaryRead,
)
from app.services import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


@router.get("", response_model=list[CandidateProfileSummaryRead])
def list_candidates(
    service: CandidateService,
    current_user: CurrentUser,
) -> list[CandidateProfileSummaryRead]:
    """List candidate identities without exposing full profile data."""
    return service.list_profiles(current_user.id)


@router.post("", response_model=CandidateProfileRead, status_code=status.HTTP_201_CREATED)
def create_candidate(
    data: CandidateProfileDetailsCreate,
    service: CandidateService,
    current_user: CurrentUser,
) -> CandidateProfileRead:
    """Create a complete candidate profile for resume tailoring."""
    return service.create_profile_with_details(data, user_id=current_user.id)


@router.get("/{candidate_id}", response_model=CandidateProfileRead)
def get_candidate(
    candidate_id: UUID,
    service: CandidateService,
    current_user: CurrentUser,
) -> CandidateProfileRead:
    """Return one complete candidate profile."""
    return service.get_profile(candidate_id, user_id=current_user.id)


@router.patch("/{candidate_id}", response_model=CandidateProfileRead)
def update_candidate(
    candidate_id: UUID,
    data: CandidateProfileDetailsUpdate,
    service: CandidateService,
    current_user: CurrentUser,
) -> CandidateProfileRead:
    """Update a candidate profile and any supplied dynamic sections."""
    return service.update_profile_with_details(candidate_id, data, user_id=current_user.id)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: UUID,
    service: CandidateService,
    current_user: CurrentUser,
) -> Response:
    """Delete a candidate profile and its owned resume data."""
    service.delete_profile(candidate_id, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
