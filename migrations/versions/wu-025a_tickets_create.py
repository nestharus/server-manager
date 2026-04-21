"""WU-025A tickets create."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_025a_tickets_create"
down_revision = "wu_024_ticket_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_version", sa.BigInteger(), nullable=False),
        sa.Column(
            "category_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reporter_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("client_ticket_id", sa.Text(), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["ticket_categories.id"],
            name="fk_tickets__category_id__ticket_categories",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("category_version >= 1", name="tickets_category_version_valid"),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="tickets_priority_valid",
        ),
    )
    op.create_index(
        "ix_tickets__category_state_created",
        "tickets",
        ["category_id", "state", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_tickets__reporter_created",
        "tickets",
        ["reporter_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_tickets__owner_state_created",
        "tickets",
        ["owner_id", "state", sa.text("created_at DESC")],
        unique=False,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_tickets__category_client_ticket_id
        ON tickets (category_id, client_ticket_id)
        WHERE client_ticket_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_tickets__category_client_ticket_id", table_name="tickets")
    op.drop_index("ix_tickets__owner_state_created", table_name="tickets")
    op.drop_index("ix_tickets__reporter_created", table_name="tickets")
    op.drop_index("ix_tickets__category_state_created", table_name="tickets")
    op.drop_table("tickets")
