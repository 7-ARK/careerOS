"""Expand the supported application lifecycle states.

Revision ID: c4f8a9d2e6b1
Revises: b7d9a4c2e1f0
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4f8a9d2e6b1"
down_revision: str | None = "b7d9a4c2e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPANDED_STATUS_CHECK = (
    "status IN ('not_applied', 'saved', 'applied', 'interviewing', 'offer', "
    "'accepted', 'rejected', 'withdrawn', 'archived')"
)
ORIGINAL_STATUS_CHECK = (
    "status IN ('not_applied', 'saved', 'applied', 'interviewing', 'rejected')"
)


def upgrade() -> None:
    with op.batch_alter_table("application_records") as batch_op:
        batch_op.drop_constraint("status_supported", type_="check")
        batch_op.create_check_constraint("status_supported", EXPANDED_STATUS_CHECK)


def downgrade() -> None:
    op.execute(
        "UPDATE application_records SET status = 'saved' "
        "WHERE status IN ('offer', 'accepted', 'withdrawn', 'archived')"
    )
    with op.batch_alter_table("application_records") as batch_op:
        batch_op.drop_constraint("status_supported", type_="check")
        batch_op.create_check_constraint("status_supported", ORIGINAL_STATUS_CHECK)
