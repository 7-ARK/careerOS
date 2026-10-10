"""Safely reset and seed the bounded recruiter-demo workspace."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import create_database_engine, create_session_factory
from app.features.document_generation import DocumentGenerationService
from app.models import (
    ApplicationHistory,
    ApplicationRecord,
    CandidateProfile,
    CareerAnalysisRun,
    GeneratedDocument,
    JobAnalysis,
    JobDescription,
    ResumeAnalysis,
    ResumeDraft,
    ResumeVersion,
)
from app.models.enums import DocumentFormat, SourcePlatform
from app.repositories import UserRepository
from app.schemas import (
    GoldenCareerAnalysisRead,
    GoldenCareerAnalysisRequest,
    GoldenCareerReviewRequest,
)
from app.services.career_analysis import GoldenCareerAnalysisService

DEMO_EMAIL = "demo@careeros.local"
DEMO_CANDIDATE_EMAIL = "amina.rahman.dev@example.com"

CANONICAL_JOB_DESCRIPTION = "\n".join(
    [
        (
            "Atlas AI Labs is hiring a Junior Applied AI Engineer for a remote early-career "
            "role supporting teams in Europe and the Middle East."
        ),
        "",
        "Required qualifications:",
        (
            "- Bachelor's degree in Artificial Intelligence, Computer Science, Machine "
            "Learning, or a related field."
        ),
        "- 0-2 years of professional, internship, or substantial project experience.",
        "- Strong Python programming and machine-learning fundamentals.",
        "- Practical experience with natural-language processing.",
        "- Build validated REST API endpoints using FastAPI and Pydantic models.",
        (
            "- Develop RAG pipelines involving chunking, embeddings, vector retrieval, and "
            "evidence citations."
        ),
        "- Integrate LLM APIs and produce schema-validated structured outputs.",
        "- Build human-in-the-loop workflows for reviewing AI-generated content.",
        "- Work with SQL and PostgreSQL.",
        "- Use Git and GitHub collaboration workflows.",
        "- Package services with Docker.",
        "- Experience with at least one agent framework: LangChain or LangGraph.",
        "",
        "Preferred qualifications:",
        "- Familiarity with AWS.",
        "- Familiarity with Kubernetes.",
        "- Experience with Django or Flask.",
        "- Basic CI/CD knowledge.",
        "",
        (
            "The engineer will implement small production-oriented AI features, write "
            "automated tests, document technical decisions, investigate failures, and "
            "collaborate with senior engineers. Applicants may demonstrate requirements "
            "through university, internship, open-source, freelance, or personal-project work."
        ),
    ]
)


class DemoResetRefusedError(RuntimeError):
    """Raised when the requested reset does not satisfy explicit safety rules."""


@dataclass(frozen=True, slots=True)
class DemoWorkspaceSnapshot:
    """Inspectable records owned by one selected demo user."""

    user_id: UUID
    email: str
    candidate_profile_ids: tuple[UUID, ...]
    candidate_names: tuple[str, ...]
    synthetic_verified: bool
    counts: dict[str, int]
    document_paths: tuple[Path, ...]
    job_description_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class DemoResetResult:
    """Dry-run or committed reset outcome."""

    dry_run: bool
    before: DemoWorkspaceSnapshot
    removed: dict[str, int]


@dataclass(frozen=True, slots=True)
class SeededDemoRecord:
    """One deterministic analysis created for recruiter demonstration."""

    run_id: UUID
    role: str
    company: str
    status: str
    evidence_coverage_score: str
    application_record_id: UUID | None


def inspect_demo_workspace(
    session: Session,
    email: str,
    *,
    allow_non_demo_target: bool = False,
    confirmation_email: str | None = None,
) -> DemoWorkspaceSnapshot:
    """Inspect one explicit owner without changing any data."""
    normalized_email = email.strip().casefold()
    _validate_target_email(
        normalized_email,
        allow_non_demo_target=allow_non_demo_target,
        confirmation_email=confirmation_email,
    )
    user = UserRepository(session).get_by_email(normalized_email)
    if user is None:
        raise DemoResetRefusedError(f"No user exists for {normalized_email}.")
    profiles = list(
        session.scalars(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .order_by(CandidateProfile.created_at)
        )
    )
    if not profiles:
        raise DemoResetRefusedError("The selected user has no candidate profile to preserve.")
    profile_ids = tuple(profile.id for profile in profiles)
    job_description_ids = _owned_job_description_ids(session, user.id, profile_ids)
    document_paths = tuple(
        Path(path)
        for path in session.scalars(
            select(GeneratedDocument.file_path).where(
                GeneratedDocument.candidate_profile_id.in_(profile_ids)
            )
        )
    )
    counts = {
        "career_analysis_runs": _count(
            session,
            CareerAnalysisRun,
            CareerAnalysisRun.user_id == user.id,
            CareerAnalysisRun.candidate_profile_id.in_(profile_ids),
        ),
        "application_records": _count(
            session,
            ApplicationRecord,
            ApplicationRecord.candidate_profile_id.in_(profile_ids),
        ),
        "generated_documents": _count(
            session,
            GeneratedDocument,
            GeneratedDocument.candidate_profile_id.in_(profile_ids),
        ),
        "resume_drafts": _count(
            session,
            ResumeDraft,
            ResumeDraft.candidate_profile_id.in_(profile_ids),
        ),
        "resume_analyses": _count(
            session,
            ResumeAnalysis,
            ResumeAnalysis.candidate_profile_id.in_(profile_ids),
        ),
        "application_history": _count(
            session,
            ApplicationHistory,
            ApplicationHistory.profile_id.in_(profile_ids),
        ),
        "resume_versions": _count(
            session,
            ResumeVersion,
            ResumeVersion.profile_id.in_(profile_ids),
        ),
        "related_job_descriptions": len(job_description_ids),
    }
    synthetic_verified = (
        normalized_email == DEMO_EMAIL
        and len(profiles) == 1
        and profiles[0].email is not None
        and profiles[0].email.casefold() == DEMO_CANDIDATE_EMAIL
    )
    return DemoWorkspaceSnapshot(
        user_id=user.id,
        email=normalized_email,
        candidate_profile_ids=profile_ids,
        candidate_names=tuple(profile.full_name for profile in profiles),
        synthetic_verified=synthetic_verified,
        counts=counts,
        document_paths=document_paths,
        job_description_ids=job_description_ids,
    )


def reset_demo_workspace(
    session: Session,
    email: str,
    *,
    dry_run: bool,
    allow_non_demo_target: bool = False,
    confirmation_email: str | None = None,
) -> DemoResetResult:
    """Dry-run or transactionally remove disposable records for one owner."""
    before = inspect_demo_workspace(
        session,
        email,
        allow_non_demo_target=allow_non_demo_target,
        confirmation_email=confirmation_email,
    )
    if dry_run:
        return DemoResetResult(dry_run=True, before=before, removed={})
    if before.email == DEMO_EMAIL and not before.synthetic_verified:
        raise DemoResetRefusedError(
            "The demo owner does not have exactly the expected fictional Amina Rahman profile."
        )

    profile_ids = before.candidate_profile_ids
    removed: dict[str, int] = {}
    try:
        removed["career_analysis_runs"] = _delete(
            session,
            CareerAnalysisRun,
            CareerAnalysisRun.user_id == before.user_id,
            CareerAnalysisRun.candidate_profile_id.in_(profile_ids),
        )
        removed["application_records"] = _delete(
            session,
            ApplicationRecord,
            ApplicationRecord.candidate_profile_id.in_(profile_ids),
        )
        removed["application_history"] = _delete(
            session,
            ApplicationHistory,
            ApplicationHistory.profile_id.in_(profile_ids),
        )
        removed["generated_documents"] = _delete(
            session,
            GeneratedDocument,
            GeneratedDocument.candidate_profile_id.in_(profile_ids),
        )
        removed["resume_drafts"] = _delete(
            session,
            ResumeDraft,
            ResumeDraft.candidate_profile_id.in_(profile_ids),
        )
        removed["resume_analyses"] = _delete(
            session,
            ResumeAnalysis,
            ResumeAnalysis.candidate_profile_id.in_(profile_ids),
        )
        removed["resume_versions"] = _delete(
            session,
            ResumeVersion,
            ResumeVersion.profile_id.in_(profile_ids),
        )
        session.flush()
        removed["related_job_descriptions"] = _delete_orphan_job_descriptions(
            session,
            before.job_description_ids,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return DemoResetResult(dry_run=False, before=before, removed=removed)


def seed_recruiter_demo_records(
    session: Session,
    *,
    user_id: UUID,
    candidate_profile_id: UUID,
    output_directory: Path,
) -> tuple[SeededDemoRecord, ...]:
    """Create three distinct deterministic runs through the production service flow."""
    service = GoldenCareerAnalysisService(session)
    service.document_generation = DocumentGenerationService(
        session,
        output_directory=output_directory,
    )

    awaiting = service.start(
        _request(
            candidate_profile_id,
            role="Backend Automation Engineer",
            company="Harborline Systems Demo",
            location="Remote",
            description=(
                "Harborline Systems Demo seeks a Backend Automation Engineer to build Python "
                "and FastAPI workflow services, maintain PostgreSQL integrations, document "
                "technical decisions, and write automated tests. Docker and browser automation "
                "experience are preferred."
            ),
        ),
        user_id=user_id,
    )
    rejected_start = service.start(
        _request(
            candidate_profile_id,
            role="AI Workflow Associate",
            company="Northwind Research Demo",
            location="Hybrid",
            description=(
                "Northwind Research Demo seeks an AI Workflow Associate to prototype Python "
                "automation, support structured-data extraction, connect reviewed API workflows, "
                "and maintain clear test evidence. Familiarity with SQL and GitHub is required."
            ),
        ),
        user_id=user_id,
    )
    rejected = service.review(
        rejected_start.id,
        GoldenCareerReviewRequest(
            decision="reject",
            review_notes="Recruiter demo example of an explicitly rejected draft.",
        ),
        user_id=user_id,
    )
    canonical_start = service.start(
        _request(
            candidate_profile_id,
            role="Junior Applied AI Engineer",
            company="Atlas AI Labs Demo",
            location="Remote - Europe / Middle East",
            description=CANONICAL_JOB_DESCRIPTION,
        ),
        user_id=user_id,
    )
    if str(canonical_start.evidence_coverage_score) != "64.29":
        raise RuntimeError(
            "Canonical recruiter fixture drifted from the required 64.29% coverage baseline."
        )
    canonical = service.review(
        canonical_start.id,
        GoldenCareerReviewRequest(
            decision="approve",
            review_notes="Reviewed fictional candidate facts and evidence citations.",
            export_formats=[DocumentFormat.DOCX, DocumentFormat.PDF],
        ),
        user_id=user_id,
    )
    return tuple(_seeded_record(item) for item in (canonical, awaiting, rejected))


def backup_file_database(database_url: str) -> Path | None:
    """Create a recoverable, consistent backup for file-based SQLite databases."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    source_path = Path(url.database).resolve()
    if not source_path.is_file():
        raise DemoResetRefusedError(f"SQLite database file was not found: {source_path}")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = source_path.with_name(
        f"{source_path.stem}.backup-{timestamp}{source_path.suffix}"
    )
    with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    return backup_path


def remove_generated_files(paths: tuple[Path, ...], *, allowed_root: Path) -> int:
    """Remove only known generated files contained by the configured output directory."""
    root = allowed_root.resolve()
    removed = 0
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            continue
        if resolved.is_file():
            resolved.unlink()
            removed += 1
    return removed


def main() -> None:
    """Run an explicit dry-run or reset-and-seed operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Exact owner email to inspect.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--dry-run", action="store_true")
    operation.add_argument("--seed", action="store_true")
    parser.add_argument("--allow-non-demo-target", action="store_true")
    parser.add_argument("--confirm-email")
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required.")
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    output_directory = Path(__file__).resolve().parents[2] / "generated" / "resumes"
    try:
        with factory() as session:
            before = inspect_demo_workspace(
                session,
                args.email,
                allow_non_demo_target=args.allow_non_demo_target,
                confirmation_email=args.confirm_email,
            )
            _print_snapshot(before)
            if args.dry_run:
                print("dry_run=true; no data was changed")
                return
            backup_path = backup_file_database(settings.database_url)
            if backup_path is not None:
                print(f"database_backup={backup_path}")
            result = reset_demo_workspace(
                session,
                args.email,
                dry_run=False,
                allow_non_demo_target=args.allow_non_demo_target,
                confirmation_email=args.confirm_email,
            )
            removed_files = remove_generated_files(
                result.before.document_paths,
                allowed_root=output_directory,
            )
            records = seed_recruiter_demo_records(
                session,
                user_id=result.before.user_id,
                candidate_profile_id=result.before.candidate_profile_ids[0],
                output_directory=output_directory,
            )
            print(f"removed={result.removed}")
            print(f"generated_files_removed={removed_files}")
            for record in records:
                print(
                    "seeded="
                    f"{record.role} | {record.company} | {record.status} | "
                    f"{record.evidence_coverage_score}%"
                )
    except DemoResetRefusedError as exc:
        raise SystemExit(f"Reset refused: {exc}") from exc
    finally:
        engine.dispose()


def _validate_target_email(
    email: str,
    *,
    allow_non_demo_target: bool,
    confirmation_email: str | None,
) -> None:
    if email == DEMO_EMAIL:
        return
    confirmed = (confirmation_email or "").strip().casefold()
    if not allow_non_demo_target or confirmed != email:
        raise DemoResetRefusedError(
            "Non-demo targets require both --allow-non-demo-target and an exact "
            "--confirm-email value."
        )


def _count(session: Session, model: type[object], *conditions: object) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def _delete(session: Session, model: type[object], *conditions: object) -> int:
    result = session.execute(delete(model).where(*conditions))
    return int(result.rowcount or 0)


def _owned_job_description_ids(
    session: Session,
    user_id: UUID,
    profile_ids: tuple[UUID, ...],
) -> tuple[UUID, ...]:
    direct_ids = {
        value
        for statement in (
            select(CareerAnalysisRun.job_description_id).where(
                CareerAnalysisRun.user_id == user_id,
                CareerAnalysisRun.candidate_profile_id.in_(profile_ids),
            ),
            select(ApplicationRecord.job_description_id).where(
                ApplicationRecord.candidate_profile_id.in_(profile_ids)
            ),
            select(ApplicationHistory.job_description_id).where(
                ApplicationHistory.profile_id.in_(profile_ids)
            ),
        )
        for value in session.scalars(statement)
        if value is not None
    }
    analysis_ids = {
        value
        for statement in (
            select(CareerAnalysisRun.job_analysis_id).where(
                CareerAnalysisRun.user_id == user_id,
                CareerAnalysisRun.candidate_profile_id.in_(profile_ids),
            ),
            select(ApplicationRecord.job_analysis_id).where(
                ApplicationRecord.candidate_profile_id.in_(profile_ids)
            ),
            select(ResumeAnalysis.job_analysis_id).where(
                ResumeAnalysis.candidate_profile_id.in_(profile_ids)
            ),
            select(ResumeDraft.job_analysis_id).where(
                ResumeDraft.candidate_profile_id.in_(profile_ids)
            ),
            select(GeneratedDocument.job_analysis_id).where(
                GeneratedDocument.candidate_profile_id.in_(profile_ids)
            ),
        )
        for value in session.scalars(statement)
        if value is not None
    }
    if analysis_ids:
        direct_ids.update(
            session.scalars(
                select(JobAnalysis.job_description_id).where(JobAnalysis.id.in_(analysis_ids))
            )
        )
    return tuple(sorted(direct_ids, key=str))


def _delete_orphan_job_descriptions(
    session: Session,
    job_description_ids: tuple[UUID, ...],
) -> int:
    removed = 0
    for job_description_id in job_description_ids:
        related_analysis_ids = select(JobAnalysis.id).where(
            JobAnalysis.job_description_id == job_description_id
        )
        remaining_references = sum(
            (
                _count(
                    session,
                    CareerAnalysisRun,
                    CareerAnalysisRun.job_description_id == job_description_id,
                ),
                _count(
                    session,
                    ApplicationRecord,
                    ApplicationRecord.job_description_id == job_description_id,
                ),
                _count(
                    session,
                    ApplicationHistory,
                    ApplicationHistory.job_description_id == job_description_id,
                ),
                _count(
                    session,
                    ResumeAnalysis,
                    ResumeAnalysis.job_analysis_id.in_(related_analysis_ids),
                ),
                _count(
                    session,
                    ResumeDraft,
                    ResumeDraft.job_analysis_id.in_(related_analysis_ids),
                ),
                _count(
                    session,
                    GeneratedDocument,
                    GeneratedDocument.job_analysis_id.in_(related_analysis_ids),
                ),
                _count(
                    session,
                    ApplicationRecord,
                    ApplicationRecord.job_analysis_id.in_(related_analysis_ids),
                ),
                _count(
                    session,
                    CareerAnalysisRun,
                    CareerAnalysisRun.job_analysis_id.in_(related_analysis_ids),
                ),
            )
        )
        if remaining_references:
            continue
        job_description = session.get(JobDescription, job_description_id)
        if job_description is not None:
            session.delete(job_description)
            session.flush()
            removed += 1
    return removed


def _request(
    candidate_profile_id: UUID,
    *,
    role: str,
    company: str,
    location: str,
    description: str,
) -> GoldenCareerAnalysisRequest:
    return GoldenCareerAnalysisRequest(
        candidate_profile_id=candidate_profile_id,
        raw_title=role,
        company_name=company,
        location=location,
        source_platform=SourcePlatform.COMPANY_SITE,
        description_text=description,
        mode="mock",
    )


def _seeded_record(analysis: GoldenCareerAnalysisRead) -> SeededDemoRecord:
    return SeededDemoRecord(
        run_id=analysis.id,
        role=analysis.structured_requirements.job_title,
        company=analysis.structured_requirements.company or "Unknown company",
        status=str(analysis.status),
        evidence_coverage_score=str(analysis.evidence_coverage_score),
        application_record_id=analysis.application_record_id,
    )


def _print_snapshot(snapshot: DemoWorkspaceSnapshot) -> None:
    print(f"target_email={snapshot.email}")
    print(f"candidate_profiles={len(snapshot.candidate_profile_ids)}")
    print(f"candidate_names={', '.join(snapshot.candidate_names)}")
    print(f"synthetic_verified={str(snapshot.synthetic_verified).lower()}")
    for name, count in snapshot.counts.items():
        print(f"would_remove_{name}={count}")


if __name__ == "__main__":
    main()
