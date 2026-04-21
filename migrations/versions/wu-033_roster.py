"""WU-033 roster lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_033_roster"
down_revision = "wu_019_chapter_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roster_entries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "roster_entries",
        sa.Column(
            "removal_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_unique_constraint(
        "uq_chapter_roles__chapter_id_id",
        "chapter_roles",
        ["chapter_id", "id"],
    )
    op.create_foreign_key(
        "fk_roster_entries__chapter_id__chapters",
        "roster_entries",
        "chapters",
        ["chapter_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_roster_entries__chapter_role_same_chapter",
        "roster_entries",
        "chapter_roles",
        ["chapter_id", "role_id"],
        ["chapter_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_roster__chapter_member_active",
        "roster_entries",
        ["chapter_id", "member_id"],
        unique=True,
        postgresql_where=sa.text("status != 'removed'"),
    )
    op.create_table(
        "roster_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("roster_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("aggregate_seq", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=False),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("from_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("originating_actor_kind", sa.Text(), nullable=True),
        sa.Column("originating_actor_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "removal_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["roster_entry_id"],
            ["roster_entries.id"],
            name="fk_roster_transitions__entry_id__roster_entries",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_roster_transitions__chapter_id__chapters",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_role_id"],
            ["chapter_roles.id"],
            name="fk_roster_transitions__from_role_id__chapter_roles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_role_id"],
            ["chapter_roles.id"],
            name="fk_roster_transitions__to_role_id__chapter_roles",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "roster_entry_id",
            "aggregate_seq",
            name="uq_roster_transitions__entry_seq",
        ),
        sa.CheckConstraint(
            "from_status IN ('active', 'on_leave', 'under_review', 'removed')",
            name="roster_transitions_from_status_valid",
        ),
        sa.CheckConstraint(
            "to_status IN ('active', 'on_leave', 'under_review', 'removed')",
            name="roster_transitions_to_status_valid",
        ),
    )
    op.create_index(
        "ix_roster_transitions__chapter_recorded",
        "roster_transitions",
        ["chapter_id", "recorded_at"],
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
        SELECT
            gen_random_uuid(),
            'roster-syncer',
            'global',
            NULL,
            '["roster.read", "roster.write"]'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'roster-syncer'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '["roster.read", "roster.write"]'::jsonb
              AND revoked_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM authority_grants
        WHERE grantee_id = 'roster-syncer'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions = '["roster.read", "roster.write"]'::jsonb
        """
    )
    op.drop_index("ix_roster_transitions__chapter_recorded", table_name="roster_transitions")
    op.drop_table("roster_transitions")
    op.drop_index("uq_roster__chapter_member_active", table_name="roster_entries")
    op.drop_constraint(
        "fk_roster_entries__chapter_role_same_chapter",
        "roster_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_roster_entries__chapter_id__chapters",
        "roster_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_chapter_roles__chapter_id_id",
        "chapter_roles",
        type_="unique",
    )
    op.drop_column("roster_entries", "removal_metadata")
    op.drop_column("roster_entries", "updated_at")
