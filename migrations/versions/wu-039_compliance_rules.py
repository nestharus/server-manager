"""WU-039 compliance rule registry."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_039_compliance_rules"
down_revision = "wu_038_permission_intent_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cadence_kind", sa.Text(), nullable=False),
        sa.Column(
            "cadence_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("evaluation_window_days", sa.Integer(), nullable=False),
        sa.Column(
            "evidence_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("consequence_kind", sa.Text(), nullable=False),
        sa.Column(
            "consequence_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "cadence_kind IN ('weekly', 'monthly', 'quarterly')",
            name="compliance_rules_cadence_kind_valid",
        ),
        sa.CheckConstraint(
            "consequence_kind IN ('review', 'under_review')",
            name="compliance_rules_consequence_kind_valid",
        ),
        sa.CheckConstraint(
            "evaluation_window_days > 0 AND evaluation_window_days <= 365",
            name="compliance_rules_evaluation_window_positive",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_requirements) = 'array'",
            name="compliance_rules_evidence_requirements_is_array",
        ),
    )
    op.create_index(
        "ux_compliance_rules__chapter_active_name",
        "compliance_rules",
        ["chapter_id", "name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_compliance_rules__chapter_active",
        "compliance_rules",
        ["chapter_id"],
        unique=False,
        postgresql_where=sa.text("active = TRUE AND archived_at IS NULL"),
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle.
    pass
