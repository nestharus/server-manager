"""WU-019 chapter lifecycle tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_019_chapter_lifecycle"
down_revision = "wu_018_chapter_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapters",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "template_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "discord_resources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["chapter_templates.id"],
            name="fk_chapters__template_id__chapter_templates",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
            name="chapters_state_valid",
        ),
    )
    op.create_index(
        "uq_chapters__name",
        "chapters",
        [sa.text("LOWER(name)")],
        unique=True,
    )
    op.create_table(
        "chapter_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("aggregate_seq", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("originating_actor_kind", sa.Text(), nullable=True),
        sa.Column("originating_actor_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_chapter_transitions__chapter_id__chapters",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "chapter_id",
            "aggregate_seq",
            name="uq_chapter_transitions__chapter_seq",
        ),
        sa.CheckConstraint(
            "from_state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
            name="chapter_transitions_from_state_valid",
        ),
        sa.CheckConstraint(
            "to_state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
            name="chapter_transitions_to_state_valid",
        ),
    )
    op.create_index(
        "ix_chapter_transitions__chapter_id",
        "chapter_transitions",
        ["chapter_id"],
        unique=False,
    )
    op.execute(
        """
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
        VALUES (
            gen_random_uuid(),
            'discord-provisioner',
            'global',
            NULL,
            '["chapter.read", "chapter.write", "chapter_template.read"]'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM authority_grants
        WHERE grantee_id = 'discord-provisioner'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions = '["chapter.read", "chapter.write", "chapter_template.read"]'::jsonb
        """
    )
    op.drop_index("ix_chapter_transitions__chapter_id", table_name="chapter_transitions")
    op.drop_table("chapter_transitions")
    op.drop_index("uq_chapters__name", table_name="chapters")
    op.drop_table("chapters")
