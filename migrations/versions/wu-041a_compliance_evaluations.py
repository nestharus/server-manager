"""WU-041A compliance evaluations and service actor grant."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_041a_compliance_evaluations"
down_revision = "wu_040a_compliance_evidence"
branch_labels = None
depends_on = None


_EVALUATOR_PERMISSIONS = (
    '["compliance_rule.read","compliance_evaluation.write","roster.transition"]'
)


def upgrade() -> None:
    op.create_table(
        "compliance_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_version", sa.BigInteger(), nullable=False),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("consequence_applied", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Text(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["compliance_rules.id"],
            name="fk_compliance_evaluations__rule_id__compliance_rules",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "result IN ('compliant', 'violation', 'insufficient_evidence')",
            name="compliance_evaluations_result_valid",
        ),
        sa.CheckConstraint(
            "consequence_applied IN ('none', 'review_queued', 'under_review_applied')",
            name="compliance_evaluations_consequence_valid",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'overridden', 'not_required')",
            name="compliance_evaluations_review_status_valid",
        ),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="compliance_evaluations_period_ordered",
        ),
        sa.CheckConstraint(
            "rule_version >= 1",
            name="compliance_evaluations_rule_version_positive",
        ),
    )
    op.create_index(
        "ux_compliance_evaluations__member_rule_period",
        "compliance_evaluations",
        ["member_id", "rule_id", "period_start", "period_end"],
        unique=True,
    )
    op.create_index(
        "ix_compliance_evaluations__rule_period",
        "compliance_evaluations",
        ["rule_id", "period_start"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_evaluations__review_pending",
        "compliance_evaluations",
        ["chapter_id", "evaluated_at"],
        unique=False,
        postgresql_where=sa.text("review_status = 'pending'"),
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
            'compliance-evaluator',
            'global',
            NULL,
            '{_EVALUATOR_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'compliance-evaluator'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '{_EVALUATOR_PERMISSIONS}'::jsonb
              AND permissions <@ '{_EVALUATOR_PERMISSIONS}'::jsonb
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        )
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle.
    pass
