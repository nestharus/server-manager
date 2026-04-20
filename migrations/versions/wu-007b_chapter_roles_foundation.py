"""WU-007B chapter roles foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_007b_chapter_roles"
down_revision = "wu_007a_chapter_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("triggers_succession", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["chapter_templates.id"],
            name="fk_chapter_roles__template_id__chapter_templates",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "chapter_id",
            "ordinal",
            name="uq_chapter_roles__chapter_id_ordinal",
        ),
    )


def downgrade() -> None:
    op.drop_table("chapter_roles")
