"""WU-028B create permission_reconciliation_runs; link drift; seed reconciler."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_028b_perm_reconciliation_runs"
down_revision = "wu_028a_perm_drift_widening"
branch_labels = None
depends_on = None


_RECONCILER_PERMISSIONS = (
    '["permission_intent.read",'
    '"permission_drift.read",'
    '"permission_drift.write",'
    '"permission_reconciliation_run.write"]'
)


def upgrade() -> None:
    op.create_table(
        "permission_reconciliation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("requested_by_kind", sa.Text(), nullable=False),
        sa.Column("requested_by_id", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "snapshot_submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'chapter')",
            name="permission_reconciliation_runs_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "(scope_kind = 'global' AND scope_id IS NULL) "
            "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
            name="permission_reconciliation_runs_scope_shape_valid",
        ),
        sa.CheckConstraint(
            "status IN ('requested','snapshot_submitted','reconciled','failed')",
            name="permission_reconciliation_runs_status_valid",
        ),
        sa.CheckConstraint(
            "("
            "status = 'requested' "
            "AND snapshot_submitted_at IS NULL "
            "AND reconciled_at IS NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'snapshot_submitted' "
            "AND snapshot_submitted_at IS NOT NULL "
            "AND reconciled_at IS NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'reconciled' "
            "AND snapshot_submitted_at IS NOT NULL "
            "AND reconciled_at IS NOT NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'failed' "
            "AND failed_at IS NOT NULL "
            "AND failure_reason IS NOT NULL "
            "AND reconciled_at IS NULL"
            ")",
            name="permission_reconciliation_runs_terminal_shape_valid",
        ),
    )

    op.create_index(
        "ix_permission_reconciliation_runs__scope",
        "permission_reconciliation_runs",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "ix_permission_reconciliation_runs__status_requested_at",
        "permission_reconciliation_runs",
        ["status", "requested_at"],
    )

    op.create_foreign_key(
        "fk_permission_drift__reconciliation_run_id",
        source_table="permission_drift",
        referent_table="permission_reconciliation_runs",
        local_cols=["reconciliation_run_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_permission_drift__run_target
            ON permission_drift (reconciliation_run_id, role_id, kind, channel_id)
            WHERE reconciliation_run_id IS NOT NULL
              AND channel_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_permission_drift__run_target_guild
            ON permission_drift (reconciliation_run_id, role_id, kind)
            WHERE reconciliation_run_id IS NOT NULL
              AND channel_id IS NULL;
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
            'permission-reconciler',
            'global',
            NULL,
            '{_RECONCILER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM authority_grants
             WHERE grantee_id = 'permission-reconciler'
               AND scope_kind = 'global'
               AND scope_id IS NULL
               AND permissions @> '{_RECONCILER_PERMISSIONS}'::jsonb
               AND permissions <@ '{_RECONCILER_PERMISSIONS}'::jsonb
               AND revoked_at IS NULL
               AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        );
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: drift rows reference the
    # run table and seeded actor grants may already be relied on by
    # operator workflows. Revocation is an explicit operator action.
    pass
