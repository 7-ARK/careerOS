"""Persistence for inspectable, human-reviewed career analysis runs."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CareerAnalysisStage, CareerAnalysisStatus


class CareerAnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store one bounded golden-flow run and its evidence-grounded output."""

    __tablename__ = "career_analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "evidence_coverage_score IS NULL OR "
            "(evidence_coverage_score >= 0 AND evidence_coverage_score <= 100)",
            name="evidence_coverage_score_range",
        ),
        CheckConstraint("estimated_cost_usd >= 0", name="estimated_cost_non_negative"),
        Index(
            "ix_career_analysis_runs_user_candidate_created",
            "user_id",
            "candidate_profile_id",
            "created_at",
        ),
        Index("ix_career_analysis_runs_status_created", "status", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
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
    resume_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("resume_analyses.id", ondelete="SET NULL"), index=True
    )
    resume_draft_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("resume_drafts.id", ondelete="SET NULL"), index=True
    )
    application_record_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("application_records.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CareerAnalysisStatus.RUNNING, index=True
    )
    current_stage: Mapped[str] = mapped_column(
        String(80), nullable=False, default=CareerAnalysisStage.PROFILE_VALIDATION
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic")
    model_name: Mapped[str | None] = mapped_column(String(200))
    token_usage: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    structured_requirements: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    evidence_matches: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_coverage_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    stage_results: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    error_details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    review_notes: Mapped[str | None] = mapped_column(Text)
