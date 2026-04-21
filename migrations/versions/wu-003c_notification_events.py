"""WU-003c notification events."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_003c_notification_events"
down_revision = "wu_003b_audit_context_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope_kind", sa.Text(), nullable=True),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "scope_kind IS NULL OR scope_kind IN ('global', 'chapter', 'member')",
            name="notification_events_scope_kind_valid",
        ),
    )
    op.create_index(
        "ix_notification_events__correlation_id",
        "notification_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events__event_type_created_at",
        "notification_events",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_events__event_type_created_at",
        table_name="notification_events",
    )
    op.drop_index("ix_notification_events__correlation_id", table_name="notification_events")
    op.drop_table("notification_events")
