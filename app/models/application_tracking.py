"""Persistence model for the lightweight application tracker."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationStatus

if TYPE_CHECKING:
    from app.models.document_generation import GeneratedDocument
    from app.models.job_analysis import JobAnalysis, JobDescription
    from app.models.knowledge_base import CandidateProfile


class ApplicationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track whether a candidate has applied to one company role."""

    __tablename__ = "application_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_applied', 'applied')",
            name="status_two_state",
        ),
        Index("ix_application_records_candidate_status", "candidate_profile_id", "status"),
        Index("ix_application_records_candidate_company", "candidate_profile_id", "company_name"),
        Index("ix_application_records_candidate_role", "candidate_profile_id", "role_title"),
    )

    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_description_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="SET NULL"), index=True
    )
    job_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="SET NULL"), index=True
    )
    generated_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("generated_documents.id", ondelete="SET NULL"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(250), nullable=False)
    role_title: Mapped[str] = mapped_column(String(250), nullable=False)
    company_email: Mapped[str | None] = mapped_column(String(320), index=True)
    job_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApplicationStatus.NOT_APPLIED, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(
        back_populates="application_records"
    )
    job_description: Mapped["JobDescription | None"] = relationship(
        back_populates="application_records"
    )
    job_analysis: Mapped["JobAnalysis | None"] = relationship(back_populates="application_records")
    generated_document: Mapped["GeneratedDocument | None"] = relationship(
        back_populates="application_records"
    )
