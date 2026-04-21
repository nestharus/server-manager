"""WU-035 application interview and waitlist lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_035_application_interview"
down_revision = "wu_042_chapter_governance"
branch_labels = None
depends_on = None


_OLD_APPLICATION_STATES = (
    "'submitted','queued','claimed','in_review','approved','denied','withdrawn'"
)
_NEW_APPLICATION_STATES = (
    "'submitted','queued','claimed','in_review','interview','waitlisted',"
    "'approved','denied','withdrawn'"
)
_OLD_REVIEW_ACTIONS = "'route','claim','review','approve','deny','withdraw'"
_NEW_REVIEW_ACTIONS = (
    "'route','claim','review','request_interview','waitlist','reactivate',"
    "'approve','deny','withdraw'"
)
_OLD_REVIEWER_ACTIONS = "'claim','review','approve','deny'"
_NEW_REVIEWER_ACTIONS = (
    "'claim','review','request_interview','waitlist','reactivate','approve','deny'"
)


def upgrade() -> None:
    op.add_column("applications", sa.Column("interview_thread_id", sa.Text(), nullable=True))

    op.drop_constraint("applications_state_valid", "applications", type_="check")
    op.create_check_constraint(
        "applications_state_valid",
        "applications",
        f"state IN ({_NEW_APPLICATION_STATES})",
    )

    op.drop_constraint("application_reviews_action_valid", "application_reviews", type_="check")
    op.create_check_constraint(
        "application_reviews_action_valid",
        "application_reviews",
        f"action IN ({_NEW_REVIEW_ACTIONS})",
    )

    op.drop_constraint(
        "application_reviews_reviewer_required",
        "application_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "application_reviews_reviewer_required",
        "application_reviews",
        f"(action IN ({_NEW_REVIEWER_ACTIONS}) AND reviewer_id IS NOT NULL) "
        "OR action IN ('route','withdraw')",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM applications
                WHERE state IN ('interview', 'waitlisted')
                   OR interview_thread_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade wu_035_application_interview with interview data';
            END IF;
            IF EXISTS (
                SELECT 1 FROM application_reviews
                WHERE action IN ('request_interview', 'waitlist', 'reactivate')
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade wu_035_application_interview with new review actions';
            END IF;
        END $$;
        """
    )

    op.drop_constraint(
        "application_reviews_reviewer_required",
        "application_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "application_reviews_reviewer_required",
        "application_reviews",
        f"(action IN ({_OLD_REVIEWER_ACTIONS}) AND reviewer_id IS NOT NULL) "
        "OR action IN ('route','withdraw')",
    )

    op.drop_constraint("application_reviews_action_valid", "application_reviews", type_="check")
    op.create_check_constraint(
        "application_reviews_action_valid",
        "application_reviews",
        f"action IN ({_OLD_REVIEW_ACTIONS})",
    )

    op.drop_constraint("applications_state_valid", "applications", type_="check")
    op.create_check_constraint(
        "applications_state_valid",
        "applications",
        f"state IN ({_OLD_APPLICATION_STATES})",
    )
    op.drop_column("applications", "interview_thread_id")
