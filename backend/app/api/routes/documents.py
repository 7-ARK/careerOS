"""Generated-document download endpoint."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import (
    CurrentUser,
    get_document_generation_service,
    get_knowledge_base_service,
)
from app.features.document_generation import DocumentGenerationService
from app.services import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
DocumentService = Annotated[
    DocumentGenerationService,
    Depends(get_document_generation_service),
]
CandidateService = Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)]


@router.get("/{document_id}/download", response_class=FileResponse)
def download_generated_document(
    document_id: UUID,
    service: DocumentService,
    candidates: CandidateService,
    current_user: CurrentUser,
) -> FileResponse:
    """Return one generated local resume file."""
    document = service.get_generated_document(document_id)
    candidates.get_profile(document.candidate_profile_id, user_id=current_user.id)
    file_path = Path(document.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="generated document file was not found")
    return FileResponse(
        path=file_path,
        filename=document.file_name,
    )
