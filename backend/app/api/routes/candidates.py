"""Candidate profile management API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.dependencies import CurrentUser, get_knowledge_base_service
from app.core.config import Settings
from app.features.resume_import import ResumeImportError, parse_resume
from app.schemas import (
    CandidateProfileDetailsCreate,
    CandidateProfileDetailsUpdate,
    CandidateProfileRead,
    CandidateProfileSummaryRead,
    ResumeImportPreview,
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
    _reject_external_preview_candidate_mutation()
    return service.create_profile_with_details(data, user_id=current_user.id)


@router.post("/import-preview", response_model=ResumeImportPreview)
async def import_candidate_resume_preview(
    _: CurrentUser,
    resume: Annotated[UploadFile, File(description="PDF or DOCX resume, up to 5 MB")],
) -> ResumeImportPreview:
    """Parse a resume in memory and return fields for explicit user review."""
    _reject_external_preview_candidate_mutation()
    try:
        content = await resume.read(5 * 1024 * 1024 + 1)
        return parse_resume(resume.filename or "resume", content)
    except ResumeImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await resume.close()


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
    _reject_external_preview_candidate_mutation()
    return service.update_profile_with_details(candidate_id, data, user_id=current_user.id)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: UUID,
    service: CandidateService,
    current_user: CurrentUser,
) -> Response:
    """Delete a candidate profile and its owned resume data."""
    _reject_external_preview_candidate_mutation()
    service.delete_profile(candidate_id, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _reject_external_preview_candidate_mutation() -> None:
    if Settings.from_env().preview_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate profile changes are disabled in external preview mode",
        )
