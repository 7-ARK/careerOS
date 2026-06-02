"""Generated-document download endpoint."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import get_document_generation_service
from app.features.document_generation import DocumentGenerationService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
DocumentService = Annotated[
    DocumentGenerationService,
    Depends(get_document_generation_service),
]


@router.get("/{document_id}/download", response_class=FileResponse)
def download_generated_document(
    document_id: UUID,
    service: DocumentService,
) -> FileResponse:
    """Return one generated local resume file."""
    document = service.get_generated_document(document_id)
    file_path = Path(document.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="generated document file was not found")
    return FileResponse(
        path=file_path,
        filename=document.file_name,
    )
