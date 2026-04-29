from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .public_intake_fixtures import (
    APPLICANT_DISCORD_USER_ID,
    assert_risk_annotation,
    applicant_receipt_token,
    count_table_rows,
    fetch_application_row,
    public_application_payload,
    seed_global_public_application_form,
    tamper_receipt_token,
)


pytestmark = pytest.mark.asyncio


@dataclass
class FakeCedarAuthorizer:
    decision: str = "Allow"
    requests: list[CedarAuthorizationRequest] = field(default_factory=list)

    def is_authorized(self, request: CedarAuthorizationRequest) -> CedarAuthorizationDecision:
        self.requests.append(request)
        return CedarAuthorizationDecision(decision=self.decision)


def _request_payload(request: CedarAuthorizationRequest) -> dict[str, str]:
    return {
        "principal": request.principal,
        "action": request.action,
        "resource": request.resource,
    }


@pytest.fixture()
def public_form(governance_db: PostgresDatabase) -> None:
    seed_global_public_application_form(governance_db)


@pytest.fixture()
def allowed_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    app.state.cedar_authorizer = authorizer
    return authorizer


@pytest.fixture()
def denied_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Deny")
    app.state.cedar_authorizer = authorizer
    return authorizer


@pytest.fixture()
def valid_applicant_receipt() -> str:
    return applicant_receipt_token()


@pytest.fixture()
def tampered_applicant_receipt(valid_applicant_receipt: str) -> str:
    return tamper_receipt_token(valid_applicant_receipt)


@pytest.fixture()
def expired_applicant_receipt() -> str:
    return applicant_receipt_token(issued_at=datetime.now(UTC) - timedelta(seconds=601))


async def _post_public_application(
    client: AsyncClient,
    *,
    receipt: str | None,
    client_application_id: str,
):
    cookies = {"applicant_receipt": receipt} if receipt is not None else None
    return await client.post(
        "/api/v1/public/applications",
        json=public_application_payload(client_application_id=client_application_id),
        cookies=cookies,
    )


def _assert_receipt_required(response) -> None:
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    body = response.json()
    assert body["code"] == "applicant_receipt_required"
    assert body["message"]


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_public_route_rejects_missing_receipt_without_mutation(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=anonymous_public_submit_remains_writable;
    level=particular-integration; source=.tmp/init-128/phase6/step6a-contract.md#C3.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="anonymous_public_submit_remains_writable",
        level="particular-integration",
        source=".tmp/init-128/phase6/step6a-contract.md#C3",
    )

    response = await _post_public_application(
        migrated_async_client,
        receipt=None,
        client_application_id="receipt-missing-route-token",
    )

    _assert_receipt_required(response)
    assert count_table_rows(governance_dsn, "members") == 0
    assert count_table_rows(governance_dsn, "applications") == 0
    assert count_table_rows(governance_dsn, "notification_events") == 0


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_public_route_rejects_tampered_receipt_without_mutation(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    tampered_applicant_receipt: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=forged_receipt_accepted;
    level=particular-integration; source=.tmp/init-128/phase6/step6a-contract.md#C2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="forged_receipt_accepted",
        level="particular-integration",
        source=".tmp/init-128/phase6/step6a-contract.md#C2",
    )

    response = await _post_public_application(
        migrated_async_client,
        receipt=tampered_applicant_receipt,
        client_application_id="receipt-tampered-route-token",
    )

    _assert_receipt_required(response)
    assert count_table_rows(governance_dsn, "members") == 0
    assert count_table_rows(governance_dsn, "applications") == 0
    assert count_table_rows(governance_dsn, "notification_events") == 0


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_public_route_rejects_expired_receipt_without_mutation(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    expired_applicant_receipt: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=expired_receipt_accepted;
    level=particular-integration; source=.tmp/init-128/phase6/step6a-contract.md#C2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="expired_receipt_accepted",
        level="particular-integration",
        source=".tmp/init-128/phase6/step6a-contract.md#C2",
    )

    response = await _post_public_application(
        migrated_async_client,
        receipt=expired_applicant_receipt,
        client_application_id="receipt-expired-route-token",
    )

    _assert_receipt_required(response)
    assert count_table_rows(governance_dsn, "members") == 0
    assert count_table_rows(governance_dsn, "applications") == 0
    assert count_table_rows(governance_dsn, "notification_events") == 0


@pytest.mark.usefixtures("public_form")
async def test_public_route_accepts_valid_receipt_without_actor_headers(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    allowed_public_route: FakeCedarAuthorizer,
    valid_applicant_receipt: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=valid_receipt_not_bound_to_real_member;
    level=particular-integration; source=.tmp/init-128/phase6/step6a-contract.md#C3.
    """
    assert_risk_annotation(
        group="TG-3",
        named_risk="valid_receipt_not_bound_to_real_member",
        level="particular-integration",
        source=".tmp/init-128/phase6/step6a-contract.md#C3",
    )

    response = await _post_public_application(
        migrated_async_client,
        receipt=valid_applicant_receipt,
        client_application_id="receipt-valid-route-token",
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()["message"] == "Application received"
    application_id = UUID(response.json()["application_id"])
    assert set(response.json()) == {"message", "application_id"}
    application = fetch_application_row(governance_dsn, application_id)
    assert application["state"] == "queued"
    assert application["applicant_kind"] == "discord"
    assert application["applicant_discord_user_id"] == APPLICANT_DISCORD_USER_ID
    assert [_request_payload(request) for request in allowed_public_route.requests] == [
        {
            "principal": 'Public::"web-intake.local"',
            "action": 'Action::"application:submit_public"',
            "resource": 'Resource::"server-manager-api:public-applications"',
        }
    ]


@pytest.mark.usefixtures("public_form")
async def test_public_route_maps_cedar_deny_to_public_forbidden_detail_with_valid_receipt(
    migrated_async_client: AsyncClient,
    denied_public_route: FakeCedarAuthorizer,
    valid_applicant_receipt: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=public_route_authz_bypass_after_receipt;
    level=particular-integration; source=.tmp/init-128/phase6/step6a-contract.md#C3.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="public_route_authz_bypass_after_receipt",
        level="particular-integration",
        source=".tmp/init-128/phase6/step6a-contract.md#C3",
    )

    response = await _post_public_application(
        migrated_async_client,
        receipt=valid_applicant_receipt,
        client_application_id="receipt-denied-route-token",
    )

    assert denied_public_route.requests
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "public_intake_forbidden"}


async def test_authenticated_application_route_still_requires_actor_headers(
    migrated_async_client: AsyncClient,
) -> None:
    """Risk annotation: group=TG-5; named_risk=authenticated_route_leaks_public_access;
    level=particular-integration; source=proposals/02-public-application-intake.md#§5 AS-6.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="authenticated_route_leaks_public_access",
        level="particular-integration",
        source="proposals/02-public-application-intake.md#§5",
    )

    response = await migrated_async_client.post(
        "/api/v1/applications",
        json=public_application_payload(client_application_id="wrong-route-token"),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    detail = response.json()["detail"]
    assert detail["code"] == "actor_identity_missing"
