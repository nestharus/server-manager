from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .chapter_selector_fixtures import (
    chapter_selector_public_payload,
    fetch_application_target_row,
    seed_chapter,
    seed_global_chapter_selector_form,
)
from .public_intake_fixtures import applicant_receipt_token


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
def allowed_public_route(app: FastAPI, override_provider) -> Iterator[FakeCedarAuthorizer]:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        yield authorizer


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
    return f"init-136-{label}-{uuid4().hex}"


def _visibility_form_fields() -> list[dict[str, Any]]:
    return [
        {
            "id": "character_name",
            "type": "short",
            "label": "Character name",
            "required": True,
            "max_length": 64,
            "page": 1,
        },
        {
            "id": "wants_officer",
            "type": "boolean",
            "label": "Interested in officer review",
            "required": True,
            "page": 1,
        },
        {
            "id": "officer_statement",
            "type": "long",
            "label": "Officer statement",
            "required": True,
            "max_length": 4000,
            "page": 2,
            "visible_when": {
                "field_id": "wants_officer",
                "op": "eq",
                "value": True,
            },
        },
        {
            "id": "application_text",
            "type": "long",
            "label": "Application text",
            "required": True,
            "max_length": 4000,
            "page": 3,
        },
    ]


def seed_global_multipage_form(db: PostgresDatabase) -> UUID:
    form_id = uuid4()
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE form_definitions
            SET status = 'archived',
                archived_at = CURRENT_TIMESTAMP
            WHERE scope_kind = 'global'
              AND scope_id IS NULL
              AND status = 'current'
            """
        )
        connection.execute(
            """
            INSERT INTO form_definitions (
                id,
                scope_kind,
                scope_id,
                version,
                name,
                target_type,
                fields,
                routing_rules,
                status,
                published_by_kind,
                published_by_id
            )
            VALUES (
                %s,
                'global',
                NULL,
                1,
                'Public multipage application',
                'chapter_membership',
                %s,
                %s,
                'current',
                'service',
                'init-136-test'
            )
            """,
            (
                form_id,
                Jsonb(_visibility_form_fields()),
                Jsonb(
                    {
                        "schema_version": 1,
                        "queue": "chapter_officers",
                        "review_scope": {"scope_kind": "global", "scope_id": None},
                    }
                ),
            ),
        )
    return form_id


def _payload(
    *,
    responses: dict[str, Any],
    client_application_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scope": {"scope_kind": "global", "scope_id": None},
        "responses": responses,
    }
    if client_application_id is not None:
        payload["client_application_id"] = client_application_id
    return payload


def _fetch_application_by_client_id(
    db: PostgresDatabase,
    client_application_id: str,
) -> dict[str, Any] | None:
    with db.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT id, responses
            FROM applications
            WHERE client_application_id = %s
            """,
            (client_application_id,),
        ).fetchone()
    return None if row is None else dict(row)


@pytest.mark.usefixtures("allowed_public_route")
async def test_required_field_on_hidden_page_may_be_omitted(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3.
    """
    seed_global_multipage_form(governance_db)
    client_id = _client_id("hidden-required-omitted")

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=client_id,
            responses={
                "character_name": "Kalec",
                "wants_officer": False,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application = _fetch_application_by_client_id(governance_db, client_id)
    assert application is not None
    assert "officer_statement" not in application["responses"]


@pytest.mark.usefixtures("allowed_public_route")
async def test_required_field_on_visible_page_must_be_present(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3.
    """
    seed_global_multipage_form(governance_db)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("visible-required-missing"),
            responses={
                "character_name": "Kalec",
                "wants_officer": True,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_visible_required_field_blank_string_still_fails_per_type_validation(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3.
    """
    seed_global_multipage_form(governance_db)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("visible-required-blank"),
            responses={
                "character_name": "Kalec",
                "wants_officer": True,
                "officer_statement": "   ",
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_always_visible_required_field_remains_required_on_final_submit(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3.
    """
    seed_global_multipage_form(governance_db)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("always-visible-missing"),
            responses={
                "character_name": "Kalec",
                "wants_officer": False,
            },
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_hidden_field_response_is_rejected_without_persisting_or_echoing_value(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3-F3.
    """
    seed_global_multipage_form(governance_db)
    client_id = _client_id("hidden-field-pii")
    hidden_value = "full legal name: Sensitive Applicant; email: hidden@example.test"

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=client_id,
            responses={
                "character_name": "Kalec",
                "wants_officer": False,
                "officer_statement": hidden_value,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert "officer_statement" in response.text
    assert hidden_value not in response.text
    assert _fetch_application_by_client_id(governance_db, client_id) is None


@pytest.mark.usefixtures("allowed_public_route")
async def test_existing_chapter_select_submit_path_still_works(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=visible_when_server_evaluates_authoritatively;
    level=component; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-3.
    """
    seed_global_chapter_selector_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Alpha", state="active")

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id("chapter-selector"),
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    row = fetch_application_target_row(governance_db, response.json()["application_id"])
    assert row["target_scope_kind"] == "chapter"
    assert row["target_scope_id"] == chapter_id
