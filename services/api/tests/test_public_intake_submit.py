from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationSubmission, PublicApplicationSubmission
from app.repositories.db import PostgresDatabase
from app.services.applications import (
    APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST,
    submit_application,
)

from .public_intake_fixtures import (
    APPLICANT_DISCORD_USER_ID,
    AUTHENTICATED_SUBMIT_SURFACE,
    PUBLIC_SUBMIT_SURFACE,
    assert_risk_annotation,
    authenticated_submission,
    create_real_member,
    fetch_application_actions,
    fetch_application_row,
    fetch_notification_materialize_effects,
    fetch_public_submitted_events,
    fetch_route_reviews,
    grant_application_submit,
    public_application_payload,
    seed_global_public_application_form,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture()
def public_form(governance_db: PostgresDatabase) -> None:
    seed_global_public_application_form(governance_db)


@pytest.fixture()
def receipt_submit_service():
    import importlib

    return importlib.import_module("app.services.applications").submit_public_application_with_receipt


@pytest.mark.usefixtures("public_form")
async def test_public_submit_with_receipt_creates_queued_application_for_real_discord_member(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    receipt_submit_service,
) -> None:
    """Risk annotation: group=TG-5; named_risk=receipt_submit_bypasses_real_member_binding;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C5.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="receipt_submit_bypasses_real_member_binding",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C5",
    )
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="receipt-service-token")
    )

    application_id = await receipt_submit_service(
        governance_db,
        submission,
        discord_user_id=APPLICANT_DISCORD_USER_ID,
    )

    assert isinstance(application_id, UUID)
    application = fetch_application_row(governance_dsn, application_id)
    assert application["id"] == application_id
    assert application["state"] == "queued"
    assert application["client_application_id"] == "receipt-service-token"
    assert application["applicant_discord_user_id"] == APPLICANT_DISCORD_USER_ID
    assert application["applicant_kind"] == "discord"
    assert application["version"] == 2
    reviews = fetch_route_reviews(governance_dsn, application_id)
    assert reviews == [
        {
            "action": "route",
            "actor_kind": "user",
            "actor_id": str(application["applicant_id"]),
        }
    ]


@pytest.mark.usefixtures("public_form")
async def test_public_submit_with_receipt_stamps_user_audit_and_notification_event(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    receipt_submit_service,
) -> None:
    """Risk annotation: group=TG-5; named_risk=receipt_submit_audit_or_event_missing;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C5-C6.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="receipt_submit_audit_or_event_missing",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C5-C6",
    )
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="receipt-audit-token")
    )

    application_id = await receipt_submit_service(
        governance_db,
        submission,
        discord_user_id=APPLICANT_DISCORD_USER_ID,
    )

    application = fetch_application_row(governance_dsn, application_id)
    actions = fetch_application_actions(governance_dsn, application_id)
    action_types = {action["action_type"] for action in actions}
    assert {"application.submit", "application.route"} <= action_types
    assert {action["actor_kind"] for action in actions} == {"user"}
    assert {action["actor_id"] for action in actions} == {str(application["applicant_id"])}
    assert {action["request_surface"] for action in actions} == {PUBLIC_SUBMIT_SURFACE}
    assert len({action["correlation_id"] for action in actions}) == 1

    submit_action = next(
        action for action in actions if action["action_type"] == "application.submit"
    )
    assert set(submit_action["request_json"]) <= set(APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST)
    assert "responses" in submit_action["request_json"]
    assert "applicant_id" in submit_action["request_json"]
    assert "state" not in submit_action["request_json"]

    events = fetch_public_submitted_events(governance_dsn, application_id=application_id)
    assert len(events) == 1
    payload = events[0]["payload_json"]
    assert payload["application_id"] == str(application_id)
    assert payload["recipient_discord_user_id"] == APPLICANT_DISCORD_USER_ID
    assert fetch_notification_materialize_effects(governance_dsn)


@pytest.mark.usefixtures("public_form")
async def test_public_submit_notification_event_targets_receipt_discord_user(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    receipt_submit_service,
) -> None:
    """Risk annotation: group=TG-6; named_risk=public_submitted_event_missing_recipient;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C6.
    """
    assert_risk_annotation(
        group="TG-6",
        named_risk="public_submitted_event_missing_recipient",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C6",
    )
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="receipt-event-token")
    )

    application_id = await receipt_submit_service(
        governance_db,
        submission,
        discord_user_id=APPLICANT_DISCORD_USER_ID,
    )

    events = fetch_public_submitted_events(governance_dsn, application_id=application_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "application.public_submitted"
    payload = events[0]["payload_json"]
    assert payload["application_id"] == str(application_id)
    assert payload["recipient_discord_user_id"] == APPLICANT_DISCORD_USER_ID


async def test_authenticated_submit_keeps_user_surface_and_authority_gate(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=adjacent_authenticated_submit_regression;
    level=component; source=planning/proposals/02-public-application-intake.md#§3 AS-6.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="adjacent_authenticated_submit_regression",
        level="component",
        source="planning/proposals/02-public-application-intake.md#§3",
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
