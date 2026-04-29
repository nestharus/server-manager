"""WU-043 members kind discriminator."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_043_members_kind"
down_revision = "wu_041a_compliance_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("kind", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE members SET kind = "
        "CASE WHEN discord_user_id LIKE 'public:%' "
        "THEN 'public_intake' ELSE 'discord' END "
        "WHERE kind IS NULL"
    )
    op.alter_column("members", "kind", nullable=False)
    op.create_check_constraint(
        "members_kind_valid",
        "members",
        "kind IN ('discord', 'public_intake')",
    )


def downgrade() -> None:
    op.drop_constraint("members_kind_valid", "members", type_="check")
    op.drop_column("members", "kind")
