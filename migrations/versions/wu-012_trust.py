"""WU-012 trust profile aggregate."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_012_trust"
down_revision = "wu_011_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trust_profiles",
        sa.Column(
            "member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column(
            "signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "policy_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("policy_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="trust_profiles_score_range",
        ),
    )
    op.create_index(
        "ix_trust_profiles__policy_version_id",
        "trust_profiles",
        ["policy_version_id"],
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
            'member-onboarder',
            'global',
            NULL,
            '["member.read", "member.write", "trust.read", "trust.write"]'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM authority_grants
            WHERE grantee_id = 'member-onboarder'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND permissions @> '["member.read", "member.write", "trust.read", "trust.write"]'::jsonb
              AND revoked_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM authority_grants
        WHERE grantee_id = 'member-onboarder'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions @> '["member.read", "member.write", "trust.read", "trust.write"]'::jsonb
        """
    )
    op.drop_index("ix_trust_profiles__policy_version_id", table_name="trust_profiles")
    op.drop_table("trust_profiles")
