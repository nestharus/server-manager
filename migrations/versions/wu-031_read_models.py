"""WU-031 read-model cursor substrate and projector grant."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_031_read_models"
down_revision = "wu_028b_perm_reconciliation_runs"
branch_labels = None
depends_on = None


_PROJECTOR_PERMISSIONS = '["read_model.write"]'


def upgrade() -> None:
    op.create_table(
        "read_model_cursors",
        sa.Column("projection_name", sa.Text(), primary_key=True),
        sa.Column(
            "last_processed_id",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "last_processed_id >= 0",
            name="read_model_cursors_last_processed_id_nonnegative",
        ),
    )

    op.execute(
        """
        INSERT INTO read_model_cursors (projection_name)
        VALUES ('operational_overview')
        ON CONFLICT (projection_name) DO NOTHING
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
            'read-model-projector',
            'global',
            NULL,
            '{_PROJECTOR_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'read-model-projector'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_PROJECTOR_PERMISSIONS}'::jsonb
              AND permissions <@ '{_PROJECTOR_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        )
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: seeded service-actor grants and
    # initialized cursor rows may already be relied on by operator workflows.
    pass
