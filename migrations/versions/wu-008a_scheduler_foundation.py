"""WU-008A scheduler foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_008a_scheduler"
down_revision = "wu_007c_roster_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("job_key", sa.Text(), nullable=False),
        sa.Column("subsystem", sa.Text(), nullable=False),
        sa.Column("handler_name", sa.Text(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("job_key", name="pk_scheduled_jobs"),
        sa.CheckConstraint(
            "status IN ('queued', 'claimed', 'completed', 'failed', 'abandoned')",
            name="scheduled_jobs_status_valid",
        ),
        sa.CheckConstraint("attempts >= 0", name="scheduled_jobs_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts > 0", name="scheduled_jobs_max_attempts_positive"),
    )
    op.create_index(
        "ix_scheduled_jobs_claimable_next_run_at",
        "scheduled_jobs",
        ["next_run_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('queued', 'claimed')"),
    )
    op.create_index(
        "ix_scheduled_jobs_subsystem",
        "scheduled_jobs",
        ["subsystem"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_jobs_subsystem", table_name="scheduled_jobs")
    op.drop_index("ix_scheduled_jobs_claimable_next_run_at", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
