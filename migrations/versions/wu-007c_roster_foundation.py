"""WU-007C roster foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_007c_roster_entries"
down_revision = "wu_007b_chapter_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roster_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["chapter_roles.id"],
            name="fk_roster_entries__role_id__chapter_roles",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'on_leave', 'under_review', 'removed')",
            name="roster_entries_status_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("roster_entries")
