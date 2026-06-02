"""Persistence metadata for locally generated resume documents."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DocumentGenerationStatus

if TYPE_CHECKING:
    from app.models.application_tracking import ApplicationRecord
    from app.models.job_analysis import JobAnalysis
    from app.models.knowledge_base import CandidateProfile
    from app.models.resume_intelligence import ResumeDraft


class GeneratedDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track one immutable local document-generation attempt."""

    __tablename__ = "generated_documents"
    __table_args__ = (
        Index("ix_generated_documents_draft_created", "resume_draft_id", "created_at"),
        Index("ix_generated_documents_candidate_created", "candidate_profile_id", "created_at"),
        Index("ix_generated_documents_job_created", "job_analysis_id", "created_at"),
    )

    resume_draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    output_format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    generation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentGenerationStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    resume_draft: Mapped["ResumeDraft"] = relationship(back_populates="generated_documents")
    candidate_profile: Mapped["CandidateProfile"] = relationship(
        back_populates="generated_documents"
    )
    job_analysis: Mapped["JobAnalysis"] = relationship(back_populates="generated_documents")
    application_records: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="generated_document"
    )
