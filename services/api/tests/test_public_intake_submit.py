from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationSubmission, PublicApplicationSubmission
from app.repositories.db import PostgresDatabase
from app.services.applications import (
    APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST,
    submit_application,
    submit_public_application,
)

from .public_intake_fixtures import (
    AUTHENTICATED_SUBMIT_SURFACE,
    PUBLIC_INTAKE_ACTOR_ID,
    PUBLIC_INTAKE_ACTOR_KIND,
    PUBLIC_SUBMIT_SURFACE,
    assert_risk_annotation,
    authenticated_submission,
    create_real_member,
    fetch_application_actions,
    fetch_application_row,
    fetch_route_reviews,
    grant_application_submit,
    public_application_payload,
    seed_global_public_application_form,
)


pytestmark = pytest.mark.asyncio


async def test_public_submit_creates_queued_application_through_lifecycle(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=parallel_submit_lifecycle;
    level=component; source=proposals/02-public-application-intake.md#§3 AS-2 AS-3 AS-6.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="parallel_submit_lifecycle",
        level="component",
        source="proposals/02-public-application-intake.md#§3",
    )
    seed_global_public_application_form(governance_db)
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="public-browser-token")
    )

    application_id = await submit_public_application(governance_db, submission)

    assert isinstance(application_id, UUID)
    application = fetch_application_row(governance_dsn, application_id)
    assert application["id"] == application_id
    assert application["state"] == "queued"
    assert application["client_application_id"] == "public-browser-token"
    assert application["applicant_discord_user_id"].startswith("public:")
    assert application["version"] == 2
    reviews = fetch_route_reviews(governance_dsn, application_id)
    assert reviews == [
        {
            "action": "route",
            "actor_kind": PUBLIC_INTAKE_ACTOR_KIND,
            "actor_id": PUBLIC_INTAKE_ACTOR_ID,
        }
    ]


async def test_public_submit_without_client_id_uses_public_idempotency_namespace(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=parallel_submit_lifecycle;
    level=component; source=proposals/02-public-application-intake.md#§3 AS-2 AS-3.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="parallel_submit_lifecycle",
        level="component",
        source="proposals/02-public-application-intake.md#§3",
    )
    seed_global_public_application_form(governance_db)
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id=None)
    )

    application_id = await submit_public_application(governance_db, submission)

    application = fetch_application_row(governance_dsn, application_id)
    assert application["client_application_id"].startswith("public:")
    UUID(application["client_application_id"].removeprefix("public:"))


async def test_authenticated_submit_keeps_user_surface_and_authority_gate(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=adjacent_authenticated_submit_regression;
    level=component; source=proposals/02-public-application-intake.md#§3 AS-6.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="adjacent_authenticated_submit_regression",
        level="component",
        source="proposals/02-public-application-intake.md#§3",
    )
    seed_global_public_application_form(governance_db)
    applicant_id = create_real_member(governance_db, "200000000000000001")
    reviewer_id = create_real_member(governance_db, "200000000000000002")
    grant_application_submit(governance_db, str(applicant_id))
    submission = ApplicationSubmission.model_validate(
        authenticated_submission(applicant_id, client_id=f"auth-{uuid4().hex}")
    )

    created = await submit_application(
        governance_db,
        submission,
        ActorIdentity(actor_kind="user", actor_id=str(applicant_id)),
    )

    actions = fetch_application_actions(governance_dsn, created.id)
    assert {action["request_surface"] for action in actions} == {
        AUTHENTICATED_SUBMIT_SURFACE
    }
    forbidden_submission = ApplicationSubmission.model_validate(
        authenticated_submission(applicant_id, client_id=f"auth-{uuid4().hex}")
    )
    with pytest.raises(Exception):
        await submit_application(
            governance_db,
            forbidden_submission,
            ActorIdentity(actor_kind="user", actor_id=str(reviewer_id)),
        )


async def test_public_submit_stamps_audit_actions_with_public_intake_actor(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=anonymous_audit_actor_gap;
    level=component; source=proposals/02-public-application-intake.md#§4 AS-2.
    """
    assert_risk_annotation(
        group="TG-4",
        named_risk="anonymous_audit_actor_gap",
        level="component",
        source="proposals/02-public-application-intake.md#§4",
    )
    seed_global_public_application_form(governance_db)
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="public-audit-token")
    )

    application_id = await submit_public_application(governance_db, submission)

    actions = fetch_application_actions(governance_dsn, application_id)
    action_types = {action["action_type"] for action in actions}
    assert {"application.submit", "application.route"} <= action_types
    assert {action["actor_kind"] for action in actions} == {PUBLIC_INTAKE_ACTOR_KIND}
    assert {action["actor_id"] for action in actions} == {PUBLIC_INTAKE_ACTOR_ID}
    assert {action["request_surface"] for action in actions} == {PUBLIC_SUBMIT_SURFACE}
    assert len({action["correlation_id"] for action in actions}) == 1

    submit_action = next(
        action for action in actions if action["action_type"] == "application.submit"
    )
    assert set(submit_action["request_json"]) <= set(APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST)
    assert "responses" in submit_action["request_json"]
    assert "applicant_id" in submit_action["request_json"]
    assert "state" not in submit_action["request_json"]
