"""WU-029A notification rules and envelopes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_029a_notifications"
down_revision = "wu_012_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trigger_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column(
            "recipients_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "template_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("actionable", sa.Boolean(), nullable=False),
        sa.Column("grouping", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
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
            "scope_kind IN ('global', 'chapter', 'member')",
            name="notification_rules_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "channel IN ('dm', 'thread', 'designated_channel')",
            name="notification_rules_channel_valid",
        ),
        sa.CheckConstraint(
            "grouping IN ('per_event', 'per_root_cause')",
            name="notification_rules_grouping_valid",
        ),
    )
    op.create_index(
        "ix_notification_rules__scope",
        "notification_rules",
        ["scope_kind", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_rules__enabled",
        "notification_rules",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "ix_notification_rules__trigger_json_gin",
        "notification_rules",
        ["trigger_json"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "notification_envelopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_version", sa.BigInteger(), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("grouping", sa.Text(), nullable=False),
        sa.Column("recipient_key", sa.Text(), nullable=False),
        sa.Column("recipient_discord_id", sa.Text(), nullable=True),
        sa.Column("recipient_display", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("destination_channel_id", sa.Text(), nullable=True),
        sa.Column(
            "template_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("rendered_title", sa.Text(), nullable=False),
        sa.Column("rendered_body", sa.Text(), nullable=False),
        sa.Column("actionable", sa.Boolean(), nullable=False),
        sa.Column(
            "delivery_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "last_error_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("discord_message_id", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
            ["rule_id"],
            ["notification_rules.id"],
            name="fk_notification_envelopes__rule_id__notification_rules",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["notification_events.id"],
            name="fk_notification_envelopes__source_event_id__notification_events",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "grouping IN ('per_event', 'per_root_cause')",
            name="notification_envelopes_grouping_valid",
        ),
        sa.CheckConstraint(
            "channel IN ('dm', 'thread', 'designated_channel')",
            name="notification_envelopes_channel_valid",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'delivered_in_flight', 'delivered', 'skipped', 'failed')",
            name="notification_envelopes_delivery_status_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="notification_envelopes_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "max_attempts > 0",
            name="notification_envelopes_max_attempts_positive",
        ),
        sa.CheckConstraint(
            "delivered_at IS NULL OR delivery_status = 'delivered'",
            name="notification_envelopes_delivered_at_matches_status",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_notification_envelopes__per_event
        ON notification_envelopes (source_event_id, rule_id, recipient_key)
        WHERE grouping = 'per_event'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_notification_envelopes__per_root_cause
        ON notification_envelopes (rule_id, root_correlation_id, recipient_key)
        WHERE grouping = 'per_root_cause'
        """
    )
    op.create_index(
        "ix_notification_envelopes__pending_delivery",
        "notification_envelopes",
        ["created_at", "id"],
        unique=False,
        postgresql_where=sa.text("delivery_status = 'pending'"),
    )
    op.create_index(
        "ix_notification_envelopes__rule_id",
        "notification_envelopes",
        ["rule_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_envelopes__source_event_id",
        "notification_envelopes",
        ["source_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_envelopes__root_correlation_id",
        "notification_envelopes",
        ["root_correlation_id"],
        unique=False,
    )
    op.execute(
        """
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
            'notification-dispatcher',
            'global',
            NULL,
            '["notification.read", "notification.deliver"]'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'notification-dispatcher'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '["notification.read", "notification.deliver"]'::jsonb
              AND permissions <@ '["notification.read", "notification.deliver"]'::jsonb
              AND revoked_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM authority_grants
        WHERE grantee_id = 'notification-dispatcher'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions @> '["notification.read", "notification.deliver"]'::jsonb
          AND permissions <@ '["notification.read", "notification.deliver"]'::jsonb
          AND revoked_at IS NULL
        """
    )
    op.drop_index(
        "ix_notification_envelopes__root_correlation_id",
        table_name="notification_envelopes",
    )
    op.drop_index(
        "ix_notification_envelopes__source_event_id",
        table_name="notification_envelopes",
    )
    op.drop_index("ix_notification_envelopes__rule_id", table_name="notification_envelopes")
    op.drop_index(
        "ix_notification_envelopes__pending_delivery",
        table_name="notification_envelopes",
    )
    op.drop_index(
        "uq_notification_envelopes__per_root_cause",
        table_name="notification_envelopes",
    )
    op.drop_index(
        "uq_notification_envelopes__per_event",
        table_name="notification_envelopes",
    )
    op.drop_table("notification_envelopes")
    op.drop_index("ix_notification_rules__trigger_json_gin", table_name="notification_rules")
    op.drop_index("ix_notification_rules__enabled", table_name="notification_rules")
    op.drop_index("ix_notification_rules__scope", table_name="notification_rules")
    op.drop_table("notification_rules")
