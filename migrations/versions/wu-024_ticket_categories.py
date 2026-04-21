"""WU-024 ticket categories."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_024_ticket_categories"
down_revision = "wu_029a_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "routing_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("privacy_level", sa.Text(), nullable=False),
        sa.Column(
            "state_machine",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "sla_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("""'{"schema_version": 1, "rules": []}'"""),
        ),
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
        sa.CheckConstraint(
            "privacy_level IN ('reporter_staff', 'staff_only')",
            name="ticket_categories_privacy_level_valid",
        ),
    )
    op.create_index(
        "uq_ticket_categories__name_ci",
        "ticket_categories",
        [sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ticket_categories__name_ci", table_name="ticket_categories")
    op.drop_table("ticket_categories")
