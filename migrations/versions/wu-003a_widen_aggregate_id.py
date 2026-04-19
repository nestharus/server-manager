"""WU-003a widen activity aggregate_id to text.

ACCESS EXCLUSIVE: each ALTER COLUMN TYPE rewrites the table and blocks
concurrent reads/writes while PostgreSQL rebuilds the dependent indexes.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_003a_widen_aggregate_id"
down_revision = "wu_002_activity_substrate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "activity_actions",
        "aggregate_id",
        existing_type=sa.BigInteger(),
        type_=sa.Text(),
        postgresql_using="aggregate_id::text",
    )
    op.alter_column(
        "activity_state_changes",
        "aggregate_id",
        existing_type=sa.BigInteger(),
        type_=sa.Text(),
        postgresql_using="aggregate_id::text",
    )
    op.alter_column(
        "aggregate_heads",
        "aggregate_id",
        existing_type=sa.BigInteger(),
        type_=sa.Text(),
        postgresql_using="aggregate_id::text",
    )


def downgrade() -> None:
    raise NotImplementedError(
        "activity aggregate_id cannot be downcast to BigInteger once governance aggregates exist",
    )
