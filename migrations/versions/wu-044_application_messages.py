"""WU-044 application messages."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_044_application_messages"
down_revision = "wu_043_members_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_seq", sa.BigInteger(), nullable=False),
        sa.Column("author_actor_kind", sa.Text(), nullable=False),
        sa.Column("author_actor_id", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("client_message_id", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_application_messages__application_id__applications",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "application_id",
            "message_seq",
            name="uq_application_messages__application_seq",
        ),
        sa.CheckConstraint(
            "visibility IN ('applicant_visible', 'officer_only')",
            name="application_messages_visibility_valid",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_application_messages__application_client_message_id
        ON application_messages (application_id, client_message_id)
        WHERE client_message_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_application_messages__application_client_message_id",
        table_name="application_messages",
    )
    op.drop_table("application_messages")
