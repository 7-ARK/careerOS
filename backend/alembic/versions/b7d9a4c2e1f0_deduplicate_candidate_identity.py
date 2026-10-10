"""Deduplicate candidate identities and enforce owner/email uniqueness.

Revision ID: b7d9a4c2e1f0
Revises: e18c8cbf35a5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d9a4c2e1f0"
down_revision: str | None = "e18c8cbf35a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROFILE_CHILDREN = (
    ("career_analysis_runs", "candidate_profile_id"),
    ("application_records", "candidate_profile_id"),
    ("generated_documents", "candidate_profile_id"),
    ("resume_drafts", "candidate_profile_id"),
    ("resume_analyses", "candidate_profile_id"),
    ("application_history", "profile_id"),
    ("resume_versions", "profile_id"),
    ("preferences", "profile_id"),
    ("career_goals", "profile_id"),
    ("certifications", "profile_id"),
    ("skills", "profile_id"),
    ("projects", "profile_id"),
    ("work_experiences", "profile_id"),
    ("education", "profile_id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id, LOWER(email)
                           ORDER BY created_at DESC, id DESC
                       ) AS duplicate_rank
                FROM candidate_profiles
                WHERE email IS NOT NULL
            ) ranked
            WHERE duplicate_rank > 1
            """
        )
    ).scalars()
    for profile_id in list(duplicates):
        for table_name, column_name in PROFILE_CHILDREN:
            bind.execute(
                sa.text(f"DELETE FROM {table_name} WHERE {column_name} = :profile_id"),
                {"profile_id": profile_id},
            )
        bind.execute(
            sa.text("DELETE FROM candidate_profiles WHERE id = :profile_id"),
            {"profile_id": profile_id},
        )

    with op.batch_alter_table("candidate_profiles") as batch_op:
        batch_op.create_unique_constraint(
            "uq_candidate_profiles_user_email",
            ["user_id", "email"],
        )


def downgrade() -> None:
    with op.batch_alter_table("candidate_profiles") as batch_op:
        batch_op.drop_constraint("uq_candidate_profiles_user_email", type_="unique")
