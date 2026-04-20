"""WU-008B deferred effect foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_008b_deferred_effect"
down_revision = "wu_008a_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deferred_effects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subsystem", sa.Text(), nullable=False),
        sa.Column("effect_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("consequence_level", sa.Text(), nullable=False),
        sa.Column("precondition_state", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deferred_effects"),
        sa.UniqueConstraint("idempotency_key", name="uq_deferred_effects__idempotency_key"),
        sa.CheckConstraint(
            "consequence_level IN ('safe', 'consequential')",
            name="deferred_effects_consequence_level_valid",
        ),
        sa.CheckConstraint(
            "precondition_state IN ('unchecked', 'valid', 'invalid')",
            name="deferred_effects_precondition_state_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'claimed', 'completed', 'failed', 'skipped')",
            name="deferred_effects_status_valid",
        ),
        sa.CheckConstraint("attempts >= 0", name="deferred_effects_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts > 0", name="deferred_effects_max_attempts_positive"),
    )
    op.create_index(
        "ix_deferred_effects_queued_subsystem",
        "deferred_effects",
        ["subsystem", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_deferred_effects_consequential_precondition",
        "deferred_effects",
        ["subsystem", "precondition_state"],
        unique=False,
        postgresql_where=sa.text(
            "status = 'queued' AND consequence_level = 'consequential'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deferred_effects_consequential_precondition",
        table_name="deferred_effects",
    )
    op.drop_index("ix_deferred_effects_queued_subsystem", table_name="deferred_effects")
    op.drop_table("deferred_effects")
