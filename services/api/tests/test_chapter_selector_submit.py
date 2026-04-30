from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .chapter_selector_fixtures import (
    CHAPTER_SELECTOR_FIELD_ID,
    chapter_selector_public_payload,
    fetch_application_target_row,
    seed_chapter,
    seed_global_chapter_selector_form,
)
from .public_intake_fixtures import (
    assert_risk_annotation,
    applicant_receipt_token,
    fetch_application_actions,
    fetch_public_submitted_events,
    public_application_payload,
    seed_global_public_application_form,
)


pytestmark = pytest.mark.asyncio

PUBLIC_SUBMIT_URL = "/api/v1/public/applications"


@dataclass
class FakeCedarAuthorizer:
    decision: str = "Allow"
    requests: list[CedarAuthorizationRequest] = field(default_factory=list)

    def is_authorized(self, request: CedarAuthorizationRequest) -> CedarAuthorizationDecision:
        self.requests.append(request)
        return CedarAuthorizationDecision(decision=self.decision)


@pytest.fixture()
def allowed_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    app.state.cedar_authorizer = authorizer
    return authorizer


async def _post_public_application(
    client: AsyncClient,
    *,
    payload: dict[str, Any],
) -> Response:
    return await client.post(
        PUBLIC_SUBMIT_URL,
        json=payload,
        cookies={"applicant_receipt": applicant_receipt_token()},
    )


def _client_id(label: str) -> str:
    return f"init-135-{label}-{uuid4().hex}"


@pytest.mark.usefixtures("allowed_public_route")
async def test_positive_1_selector_form_chapter_scope_matching_response(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3-F2.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="public_chapter_submit_uses_global_form_and_chapter_target",
        level="component",
        source=".tmp/init-135/phase6/step6a-contract.md#TG-3-F2",
    )
    seed_global_chapter_selector_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Alpha", state="active")

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id("selector-match"),
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = response.json()["application_id"]
    row = fetch_application_target_row(governance_db, application_id)
    assert row["target_scope_kind"] == "chapter"
    assert row["target_scope_id"] == chapter_id
    assert row["form_snapshot"]["scope_kind"] == "global"
    assert row["form_snapshot"]["scope_id"] is None
    assert row["form_snapshot"]["target_scope"] == {
        "scope_kind": "chapter",
        "scope_id": chapter_id,
    }


@pytest.mark.usefixtures("allowed_public_route")
@pytest.mark.parametrize(
    "responses",
    [
        pytest.param(
            {
                "character_name": "Test Applicant",
                "application_text": "I want to join scheduled guild activities.",
            },
            id="missing",
        ),
        pytest.param(
            {
                CHAPTER_SELECTOR_FIELD_ID: "different-chapter",
                "character_name": "Test Applicant",
                "application_text": "I want to join scheduled guild activities.",
            },
            id="mismatched",
        ),
    ],
)
async def test_negative_selector_form_chapter_scope_missing_or_mismatched_response(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    responses: dict[str, Any],
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3-F2.
    """
    seed_global_chapter_selector_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Bravo", state="active")

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id("selector-missing-or-mismatch"),
            responses=responses,
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_positive_3_non_selector_global_form_global_scope_uses_existing_path(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3-F2.
    """
    seed_global_public_application_form(governance_db)
    client_id = _client_id("non-selector-global")

    response = await _post_public_application(
        migrated_async_client,
        payload=public_application_payload(client_application_id=client_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    row = fetch_application_target_row(governance_db, response.json()["application_id"])
    assert row["target_scope_kind"] == "global"
    assert row["target_scope_id"] is None


@pytest.mark.usefixtures("allowed_public_route")
async def test_negative_1_non_selector_global_form_chapter_scope_uses_existing_lookup(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3-F2.
    """
    seed_global_public_application_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Charlie", state="active")
    payload = public_application_payload(client_application_id=_client_id("non-selector-chapter"))
    payload["scope"] = {"scope_kind": "chapter", "scope_id": chapter_id}

    response = await _post_public_application(
        migrated_async_client,
        payload=payload,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_negative_2_selector_form_global_scope_rejected(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3-F2.
    """
    seed_global_chapter_selector_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Delta", state="active")

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id("selector-global"),
            scope_kind="global",
            scope_id=None,
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
@pytest.mark.parametrize(
    "chapter_state",
    [
        pytest.param("proposed", id="proposed"),
        pytest.param("archived", id="archived"),
    ],
)
async def test_inactive_chapter_response_rejected(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    chapter_state: str,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3.
    """
    seed_global_chapter_selector_form(governance_db)
    chapter_id = seed_chapter(governance_db, name=f"Inactive {chapter_state}", state=chapter_state)

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id(f"inactive-{chapter_state}"),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_non_existent_chapter_response_rejected(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3.
    """
    seed_global_chapter_selector_form(governance_db)
    missing_chapter_id = f"missing-{uuid4().hex}"

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=missing_chapter_id,
            client_application_id=_client_id("missing-chapter"),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_existing_global_no_selector_submit_path_unchanged(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
    level=component; source=.tmp/init-135/phase6/step6a-contract.md#TG-3.
    """
    seed_global_public_application_form(governance_db)
    client_id = _client_id("existing-global")

    response = await _post_public_application(
        migrated_async_client,
        payload=public_application_payload(client_application_id=client_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = response.json()["application_id"]
    actions = fetch_application_actions(governance_dsn, application_id)
    action_types = {action["action_type"] for action in actions}
    assert {"application.submit", "application.route"} <= action_types
    events = fetch_public_submitted_events(governance_dsn, application_id=application_id)
    assert [event["event_type"] for event in events] == ["application.public_submitted"]
