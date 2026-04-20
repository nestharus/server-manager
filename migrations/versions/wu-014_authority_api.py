"""WU-014 authority lifecycle API."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_014_authority_api"
down_revision = "wu_008b_deferred_effect"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "authority_grants",
        sa.Column("revoked_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "authority_grants",
        sa.Column("revocation_reason", sa.Text(), nullable=True),
    )
    op.execute(
        """
        ALTER TABLE authority_grants
        ADD CONSTRAINT authority_grants_revocation_trio_check
        CHECK (
            (revoked_at IS NULL) = (revoked_by IS NULL)
            AND (revoked_at IS NULL) = (revocation_reason IS NULL)
        ) NOT VALID
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "authority_grants_revocation_trio_check",
        "authority_grants",
        type_="check",
    )
    op.drop_column("authority_grants", "revocation_reason")
    op.drop_column("authority_grants", "revoked_by")
