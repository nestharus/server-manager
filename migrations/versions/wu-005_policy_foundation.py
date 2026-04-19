"""WU-005 policy foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_005_policy_foundation"
down_revision = "wu_004_authority_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_type", sa.Text(), nullable=False),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("version_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "policy_type",
            "scope_kind",
            "scope_id",
            "version_number",
            name="uq_policy_versions__policy_scope_version",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'chapter', 'member')",
            name="policy_versions_scope_kind_valid",
        ),
    )
    op.create_index(
        "ix_policy_versions__policy_type",
        "policy_versions",
        ["policy_type", "scope_kind", "scope_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policy_versions__policy_type", table_name="policy_versions")
    op.drop_table("policy_versions")
