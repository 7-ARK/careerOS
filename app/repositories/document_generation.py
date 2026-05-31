"""Repository for local generated-document metadata."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import GeneratedDocument
from app.repositories.knowledge_base import Repository


class GeneratedDocumentRepository(Repository[GeneratedDocument]):
    """Persist and retrieve local document-generation records."""

    def __init__(self, session: Session) -> None:
        """Bind the generated-document repository."""
        super().__init__(session, GeneratedDocument)

    def create_generated_document(self, **values: object) -> GeneratedDocument:
        """Create and stage one document-generation attempt."""
        return self.create(**values)

    def list_by_candidate(
        self, candidate_profile_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[GeneratedDocument]:
        """List generated documents for one candidate."""
        return self.list(
            filters={"candidate_profile_id": candidate_profile_id},
            offset=offset,
            limit=limit,
        )

    def list_by_draft(
        self, resume_draft_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[GeneratedDocument]:
        """List generated documents for one structured resume draft."""
        return self.list(filters={"resume_draft_id": resume_draft_id}, offset=offset, limit=limit)
