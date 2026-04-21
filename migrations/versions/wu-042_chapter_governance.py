"""WU-042 chapter governance lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_042_chapter_governance"
down_revision = "wu_022_applications"
branch_labels = None
depends_on = None


_CHAPTER_STATES = (
    "'proposed', 'provisioning', 'active', 'provisioning_failed', "
    "'probation', 'archiving', 'archived'"
)
_ARCHIVER_PERMISSIONS = '["application.withdraw","authority.revoke","ticket.transition"]'


def upgrade() -> None:
    op.drop_constraint("chapters_state_valid", "chapters", type_="check")
    op.create_check_constraint(
        "chapters_state_valid",
        "chapters",
        f"state IN ({_CHAPTER_STATES})",
    )
    op.drop_constraint(
        "chapter_transitions_from_state_valid",
        "chapter_transitions",
        type_="check",
    )
    op.create_check_constraint(
        "chapter_transitions_from_state_valid",
        "chapter_transitions",
        f"from_state IN ({_CHAPTER_STATES})",
    )
    op.drop_constraint(
        "chapter_transitions_to_state_valid",
        "chapter_transitions",
        type_="check",
    )
    op.create_check_constraint(
        "chapter_transitions_to_state_valid",
        "chapter_transitions",
        f"to_state IN ({_CHAPTER_STATES})",
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chapter_transitions_reason_nonblank'
                  AND conrelid = 'chapter_transitions'::regclass
            ) THEN
                ALTER TABLE chapter_transitions
                    ADD CONSTRAINT chapter_transitions_reason_nonblank
                    CHECK (btrim(reason) <> '');
            END IF;
        END $$;
        """
    )

    op.create_table(
        "chapter_archive_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archive_reason", sa.Text(), nullable=False),
        sa.Column("initiated_by_kind", sa.Text(), nullable=False),
        sa.Column("initiated_by_id", sa.Text(), nullable=False),
        sa.Column(
            "initiated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "manual_review_items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_chapter_archive_runs__chapter_id__chapters",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','cancelled')",
            name="chapter_archive_runs_status_valid",
        ),
        sa.CheckConstraint(
            "initiated_by_kind IN ('user','service')",
            name="chapter_archive_runs_actor_kind_valid",
        ),
        sa.CheckConstraint(
            "btrim(archive_reason) <> ''",
            name="chapter_archive_runs_reason_not_blank",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(manual_review_items) = 'array'",
            name="chapter_archive_runs_manual_items_array",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) "
            "OR (status != 'completed' AND completed_at IS NULL)",
            name="chapter_archive_runs_completed_shape",
        ),
    )
    op.create_index(
        "ix_chapter_archive_runs__chapter_initiated",
        "chapter_archive_runs",
        ["chapter_id", sa.text("initiated_at DESC")],
    )
    op.create_index(
        "ix_chapter_archive_runs__correlation",
        "chapter_archive_runs",
        ["correlation_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_chapter_archive_runs__one_in_progress
            ON chapter_archive_runs (chapter_id)
            WHERE status = 'in_progress'
        """
    )

    op.add_column(
        "deferred_effects",
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_deferred_effects__correlation",
        "deferred_effects",
        ["correlation_id"],
    )
    op.execute(
        """
        CREATE INDEX ix_tickets__open_chapter_routing
            ON tickets (
                (category_snapshot #>> '{routing_scope,scope_kind}'),
                (category_snapshot #>> '{routing_scope,scope_id}'),
                created_at
            )
            WHERE terminal_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_deferred_effects__unresolved_chapter
            ON deferred_effects ((payload_json ->> 'chapter_id'), created_at)
            WHERE status IN ('queued', 'claimed', 'failed')
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
            'chapter-archiver',
            'chapter',
            NULL,
            '{_ARCHIVER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'chapter-archiver'
              AND scope_kind = 'chapter'
              AND scope_id IS NULL
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
              AND permissions @> '{_ARCHIVER_PERMISSIONS}'::jsonb
              AND '{_ARCHIVER_PERMISSIONS}'::jsonb @> permissions
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM chapters
                WHERE state IN ('probation', 'archiving', 'archived')
            ) OR EXISTS (
                SELECT 1
                FROM chapter_transitions
                WHERE from_state IN ('probation', 'archiving', 'archived')
                   OR to_state IN ('probation', 'archiving', 'archived')
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade wu_042_chapter_governance after governance states are used';
            END IF;
            IF EXISTS (SELECT 1 FROM chapter_archive_runs) THEN
                RAISE EXCEPTION
                    'cannot downgrade wu_042_chapter_governance after archive runs are recorded';
            END IF;
        END $$;
        """
    )
    # Seeding is non-reversible by design: if an identical grant existed prior,
    # we cannot safely distinguish it from the seeded row. Per AGENTS.md
    # live-server principle, leave the grant in place on downgrade; an operator
    # can revoke it manually if needed.
    op.drop_index("ix_deferred_effects__unresolved_chapter", table_name="deferred_effects")
    op.drop_index("ix_tickets__open_chapter_routing", table_name="tickets")
    op.drop_index("ix_deferred_effects__correlation", table_name="deferred_effects")
    op.drop_column("deferred_effects", "causation_id")
    op.drop_index(
        "uq_chapter_archive_runs__one_in_progress",
        table_name="chapter_archive_runs",
    )
    op.drop_index(
        "ix_chapter_archive_runs__correlation",
        table_name="chapter_archive_runs",
    )
    op.drop_index(
        "ix_chapter_archive_runs__chapter_initiated",
        table_name="chapter_archive_runs",
    )
    op.drop_table("chapter_archive_runs")
    # The chapter_transitions_reason_nonblank CHECK may have been added by this
    # migration or by an earlier one; we cannot safely distinguish. Per
    # AGENTS.md live-server principle, leave the constraint in place on
    # downgrade.
    op.drop_constraint(
        "chapter_transitions_to_state_valid",
        "chapter_transitions",
        type_="check",
    )
    op.create_check_constraint(
        "chapter_transitions_to_state_valid",
        "chapter_transitions",
        "to_state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
    )
    op.drop_constraint(
        "chapter_transitions_from_state_valid",
        "chapter_transitions",
        type_="check",
    )
    op.create_check_constraint(
        "chapter_transitions_from_state_valid",
        "chapter_transitions",
        "from_state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
    )
    op.drop_constraint("chapters_state_valid", "chapters", type_="check")
    op.create_check_constraint(
        "chapters_state_valid",
        "chapters",
        "state IN ('proposed', 'provisioning', 'active', 'provisioning_failed')",
    )
