"""WU-028A widen permission_drift for scope, target, and resolution."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_028a_perm_drift_widening"
down_revision = "wu_027_perm_intent_refinements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM permission_drift
                WHERE permission_intent_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'SLICE-014 D2: pre-existing orphaned permission_drift row; '
                    'widening refuses to synthesize a target locator.';
            END IF;
        END
        $$;
        """
    )

    op.add_column(
        "permission_drift",
        sa.Column("scope_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("scope_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("role_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("channel_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column(
            "reconciliation_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolved_by_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolved_by_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolution_reason", sa.Text(), nullable=True),
    )

    op.execute(
        """
        UPDATE permission_drift d
           SET scope_kind  = i.scope_kind,
               scope_id    = i.scope_id,
               role_id     = i.role_id,
               channel_id  = i.channel_id,
               kind        = i.kind
          FROM permission_intents i
         WHERE d.permission_intent_id = i.id
           AND d.role_id IS NULL;
        """
    )

    op.alter_column("permission_drift", "scope_kind", nullable=False)
    op.alter_column("permission_drift", "role_id", nullable=False)
    op.alter_column("permission_drift", "kind", nullable=False)

    op.create_check_constraint(
        "permission_drift_scope_kind_valid",
        "permission_drift",
        "scope_kind IN ('global', 'chapter')",
    )
    op.create_check_constraint(
        "permission_drift_kind_valid",
        "permission_drift",
        "kind IN ('guild_role', 'channel_role')",
    )
    op.create_check_constraint(
        "permission_drift_scope_shape_valid",
        "permission_drift",
        "(scope_kind = 'global' AND scope_id IS NULL) "
        "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "permission_drift_variant_shape_valid",
        "permission_drift",
        "(kind = 'guild_role' AND channel_id IS NULL) "
        "OR (kind = 'channel_role' AND channel_id IS NOT NULL)",
    )
    op.execute(
        """
        UPDATE permission_drift
           SET resolved_by_kind = 'system',
               resolved_by_id = 'legacy-migration',
               resolved_at = COALESCE(resolved_at, detected_at, CURRENT_TIMESTAMP),
               resolution_reason = 'Pre-SLICE-014 legacy row, backfilled by migration'
         WHERE status IN ('acknowledged', 'reconciled', 'accepted')
           AND resolved_by_kind IS NULL;
        """
    )

    op.create_check_constraint(
        "permission_drift_resolution_shape_valid",
        "permission_drift",
        "("
        "status = 'detected' "
        "AND resolved_by_kind IS NULL "
        "AND resolved_by_id IS NULL "
        "AND resolved_at IS NULL "
        "AND resolution_reason IS NULL"
        ") OR ("
        "status IN ('acknowledged','reconciled','accepted') "
        "AND resolved_by_kind IS NOT NULL "
        "AND resolved_by_id IS NOT NULL "
        "AND resolved_at IS NOT NULL "
        "AND resolution_reason IS NOT NULL "
        "AND btrim(resolution_reason) <> ''"
        ")",
    )

    op.create_index(
        "ix_permission_drift__scope",
        "permission_drift",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "ix_permission_drift__reconciliation_run_id",
        "permission_drift",
        ["reconciliation_run_id"],
    )
    op.create_index(
        "ix_permission_drift__role_channel_kind",
        "permission_drift",
        ["role_id", "channel_id", "kind"],
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: the widened columns hold
    # orphaned drift targets that a downgrade cannot preserve safely.
    pass
