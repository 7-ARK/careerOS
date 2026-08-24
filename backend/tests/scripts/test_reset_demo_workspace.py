"""Safety and calibration coverage for the explicit recruiter-demo reset command."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApplicationRecord, CandidateProfile, CareerAnalysisRun, User
from app.scripts.reset_demo_workspace import (
    DEMO_EMAIL,
    DemoResetRefusedError,
    inspect_demo_workspace,
    reset_demo_workspace,
    seed_recruiter_demo_records,
)
from scripts.seed_candidate import seed_candidate
from tests.support import create_test_engine, create_test_session, create_test_user


@pytest.fixture
def demo_workspace(tmp_path: Path) -> Iterator[tuple[Session, CandidateProfile, Path]]:
    engine = create_test_engine()
    session = create_test_session(engine)
    profile_read = seed_candidate(session)
    profile = session.get(CandidateProfile, profile_read.id)
    assert profile is not None
    try:
        yield session, profile, tmp_path / "documents"
    finally:
        session.close()
        engine.dispose()


def test_demo_reset_dry_run_does_not_modify_data(
    demo_workspace: tuple[Session, CandidateProfile, Path],
) -> None:
    session, profile, output_directory = demo_workspace
    seed_recruiter_demo_records(
        session,
        user_id=profile.user_id,
        candidate_profile_id=profile.id,
        output_directory=output_directory,
    )
    before = inspect_demo_workspace(session, DEMO_EMAIL)
    run_ids = set(session.scalars(select(CareerAnalysisRun.id)))

    result = reset_demo_workspace(session, DEMO_EMAIL, dry_run=True)

    after = inspect_demo_workspace(session, DEMO_EMAIL)
    assert result.dry_run is True
    assert result.removed == {}
    assert after.counts == before.counts
    assert set(session.scalars(select(CareerAnalysisRun.id))) == run_ids


def test_demo_reset_affects_only_target_and_preserves_demo_identity(
    demo_workspace: tuple[Session, CandidateProfile, Path],
) -> None:
    session, profile, output_directory = demo_workspace
    seed_recruiter_demo_records(
        session,
        user_id=profile.user_id,
        candidate_profile_id=profile.id,
        output_directory=output_directory,
    )
    other_user = create_test_user(session, email="private-owner@example.com")
    other_profile = CandidateProfile(
        user_id=other_user.id,
        full_name="Private Owner",
        email="private-owner@example.com",
    )
    session.add(other_profile)
    session.flush()
    other_application = ApplicationRecord(
        candidate_profile_id=other_profile.id,
        company_name="Private Company",
        role_title="Private Role",
        status="saved",
    )
    session.add(other_application)
    session.commit()

    result = reset_demo_workspace(session, DEMO_EMAIL, dry_run=False)

    assert result.removed["career_analysis_runs"] == 3
    assert session.get(User, profile.user_id) is not None
    assert session.get(CandidateProfile, profile.id) is not None
    assert session.get(User, other_user.id) is not None
    assert session.get(CandidateProfile, other_profile.id) is not None
    assert session.get(ApplicationRecord, other_application.id) is not None
    after = inspect_demo_workspace(session, DEMO_EMAIL)
    assert all(count == 0 for count in after.counts.values())


def test_demo_reset_is_idempotent(
    demo_workspace: tuple[Session, CandidateProfile, Path],
) -> None:
    session, profile, output_directory = demo_workspace
    seed_recruiter_demo_records(
        session,
        user_id=profile.user_id,
        candidate_profile_id=profile.id,
        output_directory=output_directory,
    )

    reset_demo_workspace(session, DEMO_EMAIL, dry_run=False)
    second = reset_demo_workspace(session, DEMO_EMAIL, dry_run=False)

    assert all(count == 0 for count in second.before.counts.values())
    assert all(count == 0 for count in second.removed.values())


def test_non_demo_target_is_refused_without_exact_override(
    demo_workspace: tuple[Session, CandidateProfile, Path],
) -> None:
    session, _profile, _output_directory = demo_workspace
    create_test_user(session, email="private-owner@example.com")

    with pytest.raises(DemoResetRefusedError, match="Non-demo targets"):
        reset_demo_workspace(session, "private-owner@example.com", dry_run=True)


def test_seeded_records_are_distinct_and_preserve_canonical_calibration(
    demo_workspace: tuple[Session, CandidateProfile, Path],
) -> None:
    session, profile, output_directory = demo_workspace

    records = seed_recruiter_demo_records(
        session,
        user_id=profile.user_id,
        candidate_profile_id=profile.id,
        output_directory=output_directory,
    )

    assert len(records) == 3
    assert len({(record.role, record.company) for record in records}) == 3
    assert {record.status for record in records} == {"completed", "awaiting_review", "rejected"}
    canonical = next(record for record in records if record.role == "Junior Applied AI Engineer")
    assert canonical.evidence_coverage_score == "64.29"
    assert canonical.application_record_id is not None
    application = session.get(ApplicationRecord, canonical.application_record_id)
    assert application is not None
    assert str(application.evidence_coverage_score) == canonical.evidence_coverage_score

    run = session.get(CareerAnalysisRun, canonical.run_id)
    assert run is not None
    assert run.application_record_id == canonical.application_record_id
    matches = run.evidence_matches["match_explanation"]["requirement_matches"]
    assert len(matches) == 16
    statuses = [match["status"] for match in matches]
    assert statuses.count("matched") == 6
    assert statuses.count("partially_matched") == 6
    assert statuses.count("not_evidenced") == 4
    cloud_controls = {
        match["requirement"]["text"]: match["status"]
        for match in matches
        if any(
            term in match["requirement"]["text"]
            for term in ("AWS", "Kubernetes", "Django or Flask", "CI/CD")
        )
    }
    assert set(cloud_controls.values()) == {"not_evidenced"}
    experience = next(
        match
        for match in matches
        if match["requirement"]["text"].startswith("0-2 years")
    )
    assert experience["status"] == "partially_matched"
    assert "which exceeds the stated 0-2 year range" in experience["explanation"]
    assert "range fit is not exact" in experience["explanation"]
