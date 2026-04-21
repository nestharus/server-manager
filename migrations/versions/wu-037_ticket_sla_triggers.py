"""WU-037 ticket SLA triggers."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_037_ticket_sla_triggers"
down_revision = "wu_025c_ticket_messages"
branch_labels = None
depends_on = None


_SLA_WORKER_PERMISSIONS = '["notification.deliver", "ticket.read", "ticket.transition"]'


def upgrade() -> None:
    op.create_table(
        "ticket_sla_triggers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("threshold_seconds", sa.Integer(), nullable=False),
        sa.Column("consequence", sa.Text(), nullable=False),
        sa.Column("target_state", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "effect_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_sla_triggers__ticket_id__tickets",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticket_id",
            "rule_key",
            "threshold_seconds",
            name="uq_ticket_sla_triggers__ticket_rule_threshold",
        ),
        sa.CheckConstraint(
            "char_length(rule_key) BETWEEN 1 AND 64",
            name="ticket_sla_triggers_rule_key_length",
        ),
        sa.CheckConstraint(
            "threshold_seconds > 0",
            name="ticket_sla_triggers_threshold_positive",
        ),
        sa.CheckConstraint(
            "elapsed_seconds >= threshold_seconds",
            name="ticket_sla_triggers_elapsed_reached_threshold",
        ),
        sa.CheckConstraint(
            "consequence IN ('notify_owner','notify_scope','flag_for_review','auto_escalate')",
            name="ticket_sla_triggers_consequence_valid",
        ),
    )
    op.create_index(
        "ix_ticket_sla_triggers__ticket_applied",
        "ticket_sla_triggers",
        ["ticket_id", sa.text("applied_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_ticket_sla_triggers__rule_threshold",
        "ticket_sla_triggers",
        ["rule_key", "threshold_seconds"],
        unique=False,
    )
    op.create_index(
        "ix_ticket_sla_triggers__applied_at",
        "ticket_sla_triggers",
        [sa.text("applied_at DESC")],
        unique=False,
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
            'sla-worker',
            'global',
            NULL,
            '{_SLA_WORKER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'sla-worker'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_SLA_WORKER_PERMISSIONS}'::jsonb
              AND permissions <@ '{_SLA_WORKER_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        )
        """
    )


def downgrade() -> None:
    # The service-actor grant is intentionally not removed on downgrade. A live
    # server cannot distinguish a seeded row from an operator-created identical
    # active grant, so revocation remains an explicit operator action.
    op.drop_index("ix_ticket_sla_triggers__applied_at", table_name="ticket_sla_triggers")
    op.drop_index(
        "ix_ticket_sla_triggers__rule_threshold",
        table_name="ticket_sla_triggers",
    )
    op.drop_index(
        "ix_ticket_sla_triggers__ticket_applied",
        table_name="ticket_sla_triggers",
    )
    op.drop_table("ticket_sla_triggers")
