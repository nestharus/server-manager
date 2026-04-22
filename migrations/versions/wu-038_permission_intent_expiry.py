"""WU-038 permission intent expiry lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_038_permission_intent_expiry"
down_revision = "wu_031_read_models"
branch_labels = None
depends_on = None


_EXPIRER_PERMISSIONS = '["permission_intent.write","permission_drift.write"]'


def upgrade() -> None:
    op.add_column(
        "permission_intents",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "permission_intents_expiry_order_valid",
        "permission_intents",
        "expired_at IS NULL OR expired_at >= expires_at",
    )
    op.create_index(
        "ix_permission_intents__expired_at_pending",
        "permission_intents",
        ["expired_at"],
        unique=False,
        postgresql_where=sa.text("temporary AND expired_at IS NULL"),
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
            'permission-expirer',
            'global',
            NULL,
            '{_EXPIRER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'permission-expirer'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_EXPIRER_PERMISSIONS}'::jsonb
              AND permissions <@ '{_EXPIRER_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        )
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: live service-actor grants and
    # expiry lifecycle data may already be relied on by operator workflows.
    pass
