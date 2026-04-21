"""WU-025B ticket transitions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_025b_ticket_transitions"
down_revision = "wu_025a_tickets_create"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_seq", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("originating_actor_kind", sa.Text(), nullable=True),
        sa.Column("originating_actor_id", sa.Text(), nullable=True),
        sa.Column("from_owner_id", sa.Text(), nullable=True),
        sa.Column("to_owner_id", sa.Text(), nullable=True),
        sa.Column("from_priority", sa.Text(), nullable=True),
        sa.Column("to_priority", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_transitions__ticket_id__tickets",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticket_id",
            "aggregate_seq",
            name="uq_ticket_transitions__ticket_seq",
        ),
    )
    op.create_index(
        "ix_ticket_transitions__ticket_recorded",
        "ticket_transitions",
        ["ticket_id", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_transitions__ticket_recorded",
        table_name="ticket_transitions",
    )
    op.drop_table("ticket_transitions")
