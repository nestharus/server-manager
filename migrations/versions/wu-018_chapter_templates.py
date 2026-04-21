"""WU-018 chapter template versioning."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_018_chapter_templates"
down_revision = "wu_014_authority_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column(
        "chapter_templates",
        sa.Column("template_family_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapter_templates",
        sa.Column("version", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        UPDATE chapter_templates
        SET template_family_id = id,
            version = 1
        WHERE template_family_id IS NULL
        """
    )
    op.alter_column("chapter_templates", "template_family_id", nullable=False)
    op.alter_column("chapter_templates", "version", nullable=False)
    op.create_index(
        "uq_chapter_templates__family_version",
        "chapter_templates",
        ["template_family_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_chapter_templates__family",
        "chapter_templates",
        ["template_family_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chapter_templates__family", table_name="chapter_templates")
    op.drop_index("uq_chapter_templates__family_version", table_name="chapter_templates")
    op.drop_column("chapter_templates", "version")
    op.drop_column("chapter_templates", "template_family_id")
