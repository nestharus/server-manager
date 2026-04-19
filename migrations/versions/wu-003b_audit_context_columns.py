"""WU-003b audit correlation columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_003b_audit_context_columns"
down_revision = "wu_003a_widen_aggregate_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_actions",
        sa.Column(
            "correlation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
        ),
    )
    op.add_column(
        "activity_actions",
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "activity_actions",
        sa.Column("scope_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "activity_actions",
        sa.Column("scope_id", sa.Text(), nullable=True),
    )
    op.alter_column("activity_actions", "correlation_id", server_default=None)
    op.create_index(
        "ix_activity_actions__correlation_id",
        "activity_actions",
        ["correlation_id"],
        unique=False,
    )
    op.create_check_constraint(
        "activity_actions_scope_kind_valid",
        "activity_actions",
        "scope_kind IS NULL OR scope_kind IN ('global', 'chapter', 'member')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_activity_actions__activity_actions_scope_kind_valid",
        "activity_actions",
        type_="check",
    )
    op.drop_index("ix_activity_actions__correlation_id", table_name="activity_actions")
    op.drop_column("activity_actions", "scope_id")
    op.drop_column("activity_actions", "scope_kind")
    op.drop_column("activity_actions", "causation_id")
    op.drop_column("activity_actions", "correlation_id")
