"""WU-006A permission intents foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_006a_permission_intents"
down_revision = "wu_005_policy_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("channel_id", sa.Text(), nullable=True),
        sa.Column("permission_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("allow_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("deny_bits", sa.Numeric(precision=39, scale=0), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("temporary", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "kind IN ('guild_role', 'channel_role')",
            name="permission_intents_kind_valid",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'chapter', 'member')",
            name="permission_intents_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "(temporary AND expires_at IS NOT NULL) "
            "OR (NOT temporary AND expires_at IS NULL)",
            name="permission_intents_temporary_shape_valid",
        ),
        sa.CheckConstraint(
            "("
            "kind = 'guild_role' "
            "AND channel_id IS NULL "
            "AND permission_bits IS NOT NULL "
            "AND allow_bits IS NULL "
            "AND deny_bits IS NULL"
            ") OR ("
            "kind = 'channel_role' "
            "AND channel_id IS NOT NULL "
            "AND permission_bits IS NULL "
            "AND allow_bits IS NOT NULL "
            "AND deny_bits IS NOT NULL"
            ")",
            name="permission_intents_variant_shape_valid",
        ),
    )
    op.create_index(
        "ix_permission_intents__scope_kind",
        "permission_intents",
        ["scope_kind", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_permission_intents__role_id",
        "permission_intents",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "ix_permission_intents__expires_at",
        "permission_intents",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("temporary"),
    )


def downgrade() -> None:
    op.drop_index("ix_permission_intents__expires_at", table_name="permission_intents")
    op.drop_index("ix_permission_intents__role_id", table_name="permission_intents")
    op.drop_index("ix_permission_intents__scope_kind", table_name="permission_intents")
    op.drop_table("permission_intents")
