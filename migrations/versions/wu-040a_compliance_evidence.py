"""WU-040A compliance evidence intake."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_040a_compliance_evidence"
down_revision = "wu_039_compliance_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("chapter_id", sa.Text(), nullable=False),
        sa.Column("attachment_ref", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "extracted_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "extracted_fields_corrected",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("extraction_status", sa.Text(), nullable=False),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("submitted_by_member_id", sa.Text(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("corrected_by_member_id", sa.Text(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["compliance_rules.id"],
            name="fk_evidence_submissions__rule_id__compliance_rules",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "char_length(attachment_ref) > 0",
            name="evidence_submissions_attachment_ref_non_blank",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'running', 'completed', 'failed', 'corrected')",
            name="evidence_submissions_extraction_status_valid",
        ),
        sa.CheckConstraint(
            "extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="evidence_submissions_confidence_bounded",
        ),
        sa.CheckConstraint(
            "extraction_status <> 'completed' OR (raw_text IS NOT NULL AND extracted_fields IS NOT NULL)",
            name="evidence_submissions_completed_requires_ocr",
        ),
        sa.CheckConstraint(
            "extraction_status <> 'failed' OR extraction_error IS NOT NULL",
            name="evidence_submissions_failed_requires_error",
        ),
        sa.CheckConstraint(
            "extraction_status <> 'corrected' OR ("
            "extracted_fields_corrected IS NOT NULL "
            "AND corrected_by_member_id IS NOT NULL "
            "AND corrected_at IS NOT NULL "
            "AND correction_reason IS NOT NULL)",
            name="evidence_submissions_corrected_requires_overlay",
        ),
    )
    op.create_index(
        "ix_evidence_submissions__rule_member",
        "evidence_submissions",
        ["rule_id", "member_id", "submitted_at"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_submissions__chapter_period",
        "evidence_submissions",
        ["chapter_id", "submitted_at"],
        unique=False,
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle.
    pass
