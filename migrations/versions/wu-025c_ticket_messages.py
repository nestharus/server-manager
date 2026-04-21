"""WU-025C ticket messages."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_025c_ticket_messages"
down_revision = "wu_025b_ticket_transitions"
branch_labels = None
depends_on = None


_SERVICE_PERMISSIONS = '["ticket.create", "ticket.message.append"]'


def upgrade() -> None:
    op.create_table(
        "ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_seq", sa.BigInteger(), nullable=False),
        sa.Column("author_actor_kind", sa.Text(), nullable=False),
        sa.Column("author_actor_id", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("client_message_id", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_messages__ticket_id__tickets",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticket_id",
            "message_seq",
            name="uq_ticket_messages__ticket_seq",
        ),
        sa.CheckConstraint(
            "visibility IN ('reporter_visible', 'staff_only')",
            name="ticket_messages_visibility_valid",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ticket_messages__ticket_client_message_id
        ON ticket_messages (ticket_id, client_message_id)
        WHERE client_message_id IS NOT NULL
        """
    )
    op.execute(
        f"""
        INSERT INTO authority_grants (
            id,
            grantee_id,
            scope_kind,
            scope_id,
            permissions,
            expires_at,
            revoked_at,
            revoked_by,
            revocation_reason,
            predecessor_grant_id
        )
        SELECT
            gen_random_uuid(),
            'discord-ticket-bot',
            'global',
            NULL,
            '{_SERVICE_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'discord-ticket-bot'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_SERVICE_PERMISSIONS}'::jsonb
              AND permissions <@ '{_SERVICE_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM authority_grants
        WHERE grantee_id = 'discord-ticket-bot'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions @> '{_SERVICE_PERMISSIONS}'::jsonb
          AND permissions <@ '{_SERVICE_PERMISSIONS}'::jsonb
          AND revoked_at IS NULL
        """
    )
    op.drop_index(
        "uq_ticket_messages__ticket_client_message_id",
        table_name="ticket_messages",
    )
    op.drop_table("ticket_messages")
