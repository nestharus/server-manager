"""WU-006B permission drift foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_006b_permission_drift"
down_revision = "wu_006a_permission_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_drift",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("permission_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intent_version", sa.BigInteger(), nullable=True),
        sa.Column("actual_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("actual_allow_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("actual_deny_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("intended_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column(
            "intended_allow_bits",
            sa.Numeric(precision=39, scale=0),
            nullable=True,
        ),
        sa.Column(
            "intended_deny_bits",
            sa.Numeric(precision=39, scale=0),
            nullable=True,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["permission_intent_id"],
            ["permission_intents.id"],
            name="fk_permission_drift__permission_intent_id__permission_intents",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('detected', 'acknowledged', 'reconciled', 'accepted')",
            name="permission_drift_status_valid",
        ),
        sa.CheckConstraint(
            "("
            "permission_intent_id IS NOT NULL AND intent_version IS NOT NULL"
            ") OR ("
            "permission_intent_id IS NULL AND intent_version IS NULL"
            ")",
            name="permission_drift_intent_anchor_valid",
        ),
    )
    op.create_index(
        "ix_permission_drift__permission_intent_id",
        "permission_drift",
        ["permission_intent_id"],
        unique=False,
    )
    op.create_index(
        "ix_permission_drift__status",
        "permission_drift",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_permission_drift__detected_at",
        "permission_drift",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_permission_drift__detected_at", table_name="permission_drift")
    op.drop_index("ix_permission_drift__status", table_name="permission_drift")
    op.drop_index(
        "ix_permission_drift__permission_intent_id",
        table_name="permission_drift",
    )
    op.drop_table("permission_drift")
