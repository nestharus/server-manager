"""WU-021 application form definitions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_021_forms"
down_revision = "wu_030b_trust_profile_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("routing_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("published_by_kind", sa.Text(), nullable=False),
        sa.Column("published_by_id", sa.Text(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("version >= 1", name="form_definitions_version_positive"),
        sa.CheckConstraint(
            "scope_kind IN ('global','chapter','member')",
            name="form_definitions_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "(scope_kind = 'global' AND scope_id IS NULL) "
            "OR (scope_kind IN ('chapter','member') AND scope_id IS NOT NULL)",
            name="form_definitions_scope_shape_valid",
        ),
        sa.CheckConstraint(
            "target_type IN ("
            "'chapter_membership','officer_candidacy','role_assignment','custom'"
            ")",
            name="form_definitions_target_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('current','archived')",
            name="form_definitions_status_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(fields) = 'array'",
            name="form_definitions_fields_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(routing_rules) = 'object'",
            name="form_definitions_routing_rules_object",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_form_definitions__scope_version
            ON form_definitions (scope_kind, scope_id, version) NULLS NOT DISTINCT
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_form_definitions__current_per_scope
            ON form_definitions (scope_kind, scope_id) NULLS NOT DISTINCT
            WHERE status = 'current'
        """
    )
    op.create_index(
        "ix_form_definitions__current_lookup",
        "form_definitions",
        ["scope_kind", "scope_id", "status", sa.text("version DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_form_definitions__current_lookup", table_name="form_definitions")
    op.execute("DROP INDEX ux_form_definitions__current_per_scope")
    op.execute("DROP INDEX ux_form_definitions__scope_version")
    op.drop_table("form_definitions")
