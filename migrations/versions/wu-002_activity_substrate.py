"""WU-002 activity substrate."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_002_activity_substrate"
down_revision = "wu_001_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_actions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("request_surface", sa.Text(), nullable=False),
        sa.Column(
            "request_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column(
            "error_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected', 'failed')",
            name="activity_actions_status_valid",
        ),
    )
    op.create_index(
        "ix_activity_actions__status",
        "activity_actions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_activity_actions__actor_kind",
        "activity_actions",
        ["actor_kind"],
        unique=False,
    )
    op.create_index(
        "ix_activity_actions__aggregate_id",
        "activity_actions",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )

    op.create_table(
        "activity_state_changes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("action_id", sa.BigInteger(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.BigInteger(), nullable=False),
        sa.Column("aggregate_seq", sa.BigInteger(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "diff_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["activity_actions.id"],
            name="fk_activity_state_changes__action_id__activity_actions",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_seq",
            name="uq_activity_state_changes__aggregate_seq",
        ),
    )
    op.create_index(
        "ix_activity_state_changes__aggregate_id",
        "activity_state_changes",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )

    op.create_table(
        "aggregate_heads",
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "current_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("latest_change_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["latest_change_id"],
            ["activity_state_changes.id"],
            name="fk_aggregate_heads__latest_change_id__activity_state_changes",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "aggregate_type",
            "aggregate_id",
            name="pk_aggregate_heads",
        ),
    )


def downgrade() -> None:
    op.drop_table("aggregate_heads")
    op.drop_index("ix_activity_state_changes__aggregate_id", table_name="activity_state_changes")
    op.drop_table("activity_state_changes")
    op.drop_index("ix_activity_actions__aggregate_id", table_name="activity_actions")
    op.drop_index("ix_activity_actions__actor_kind", table_name="activity_actions")
    op.drop_index("ix_activity_actions__status", table_name="activity_actions")
    op.drop_table("activity_actions")
