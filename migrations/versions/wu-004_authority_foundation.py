"""WU-004 authority foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_004_authority_foundation"
down_revision = "wu_003c_notification_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authority_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("grantee_id", sa.Text(), nullable=False),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("predecessor_grant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_grant_id"],
            ["authority_grants.id"],
            name="fk_authority_grants__predecessor_grant_id__authority_grants",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="authority_grants_revoked_after_created",
        ),
        sa.CheckConstraint(
            "predecessor_grant_id IS NULL OR predecessor_grant_id != id",
            name="authority_grants_predecessor_not_self",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'chapter', 'member')",
            name="authority_grants_scope_kind_valid",
        ),
    )
    op.create_index(
        "ix_authority_grants__grantee_id",
        "authority_grants",
        ["grantee_id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_grants__scope_kind",
        "authority_grants",
        ["scope_kind", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_grants__expires_at",
        "authority_grants",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_authority_grants__expires_at", table_name="authority_grants")
    op.drop_index("ix_authority_grants__scope_kind", table_name="authority_grants")
    op.drop_index("ix_authority_grants__grantee_id", table_name="authority_grants")
    op.drop_table("authority_grants")
