"""WU-022 application intake lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_022_applications"
down_revision = "wu_021_forms"
branch_labels = None
depends_on = None

_DISCORD_MEMBER_READ_PERMISSIONS = '["member.read"]'


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("applicant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("form_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("form_version", sa.BigInteger(), nullable=False),
        sa.Column("form_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_scope_kind", sa.Text(), nullable=False),
        sa.Column("target_scope_id", sa.Text(), nullable=True),
        sa.Column("responses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("client_application_id", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["members.id"],
            name="fk_applications__applicant_id__members",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["form_definition_id"],
            ["form_definitions.id"],
            name="fk_applications__form_definition_id__form_definitions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["members.id"],
            name="fk_applications__owner_id__members",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("form_version >= 1", name="applications_form_version_positive"),
        sa.CheckConstraint(
            "state IN ('submitted','queued','claimed','in_review','approved','denied','withdrawn')",
            name="applications_state_valid",
        ),
        sa.CheckConstraint(
            "target_scope_kind IN ('global','chapter','member')",
            name="applications_target_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "(target_scope_kind = 'global' AND target_scope_id IS NULL) "
            "OR (target_scope_kind IN ('chapter','member') AND target_scope_id IS NOT NULL)",
            name="applications_target_scope_shape_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(form_snapshot) = 'object'",
            name="applications_form_snapshot_object",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(responses) = 'object'",
            name="applications_responses_object",
        ),
        sa.CheckConstraint(
            "state NOT IN ('approved','denied') "
            "OR (decision_reason IS NOT NULL AND btrim(decision_reason) <> '')",
            name="applications_decision_reason_required",
        ),
    )
    op.create_index(
        "ix_applications__queue",
        "applications",
        ["state", "target_scope_kind", "target_scope_id", sa.text("created_at ASC")],
    )
    op.create_index(
        "ix_applications__owner_state",
        "applications",
        ["owner_id", "state", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_applications__applicant_created",
        "applications",
        ["applicant_id", sa.text("created_at DESC")],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_applications__applicant_client_application
            ON applications (applicant_id, client_application_id)
            WHERE client_application_id IS NOT NULL
        """
    )

    op.create_table(
        "application_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_seq", sa.BigInteger(), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_application_reviews__application_id__applications",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["members.id"],
            name="fk_application_reviews__reviewer_id__members",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "application_id",
            "aggregate_seq",
            name="uq_application_reviews__application_seq",
        ),
        sa.CheckConstraint(
            "action IN ('route','claim','review','approve','deny','withdraw')",
            name="application_reviews_action_valid",
        ),
        sa.CheckConstraint(
            "(action IN ('claim','review','approve','deny') AND reviewer_id IS NOT NULL) "
            "OR action IN ('route','withdraw')",
            name="application_reviews_reviewer_required",
        ),
    )
    op.create_index(
        "ix_application_reviews__application_seq",
        "application_reviews",
        ["application_id", sa.text("aggregate_seq ASC")],
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
            'discord-ticket-bot',
            'global',
            NULL,
            '{_DISCORD_MEMBER_READ_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'discord-ticket-bot'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_DISCORD_MEMBER_READ_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM authority_grants
        WHERE grantee_id = 'discord-ticket-bot'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions = '{_DISCORD_MEMBER_READ_PERMISSIONS}'::jsonb
        """
    )
    op.drop_index(
        "ix_application_reviews__application_seq",
        table_name="application_reviews",
    )
    op.drop_table("application_reviews")
    op.execute("DROP INDEX ux_applications__applicant_client_application")
    op.drop_index("ix_applications__applicant_created", table_name="applications")
    op.drop_index("ix_applications__owner_state", table_name="applications")
    op.drop_index("ix_applications__queue", table_name="applications")
    op.drop_table("applications")
