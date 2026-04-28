from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .public_intake_fixtures import (
    assert_risk_annotation,
    public_application_payload,
    seed_global_public_application_form,
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


async def test_public_route_accepts_valid_body_without_actor_headers(
    app: FastAPI,
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=public_route_depends_on_actor_headers;
    level=particular-integration; source=proposals/02-public-application-intake.md#§5 AS-1 AS-4.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="public_route_depends_on_actor_headers",
        level="particular-integration",
        source="proposals/02-public-application-intake.md#§5",
    )
    seed_global_public_application_form(governance_db)
    authorizer = FakeCedarAuthorizer(decision="Allow")
    app.state.cedar_authorizer = authorizer

    response = await migrated_async_client.post(
        "/api/v1/public/applications",
        json=public_application_payload(client_application_id="public-route-token"),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()["message"] == "Application received"
    UUID(response.json()["application_id"])
    assert set(response.json()) == {"message", "application_id"}
    assert [_request_payload(request) for request in authorizer.requests] == [
        {
            "principal": 'Public::"web-intake.local"',
            "action": 'Action::"application:submit_public"',
            "resource": 'Resource::"server-manager-api:public-applications"',
        }
    ]


async def test_public_route_rejects_malformed_payload(
    app: FastAPI,
    migrated_async_client: AsyncClient,
) -> None:
    """Risk annotation: group=TG-5; named_risk=public_route_validation_gap;
    level=particular-integration; source=proposals/02-public-application-intake.md#§5 AS-1.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="public_route_validation_gap",
        level="particular-integration",
        source="proposals/02-public-application-intake.md#§5",
    )
    app.state.cedar_authorizer = FakeCedarAuthorizer(decision="Allow")

    response = await migrated_async_client.post(
        "/api/v1/public/applications",
        json={"character_name": "old flat payload"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_public_route_maps_cedar_deny_to_public_forbidden_detail(
    app: FastAPI,
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=public_route_authz_bypass;
    level=particular-integration; source=proposals/02-public-application-intake.md#§5 AS-4.
    """
    assert_risk_annotation(
        group="TG-5",
        named_risk="public_route_authz_bypass",
        level="particular-integration",
        source="proposals/02-public-application-intake.md#§5",
    )
    seed_global_public_application_form(governance_db)
    app.state.cedar_authorizer = FakeCedarAuthorizer(decision="Deny")

    response = await migrated_async_client.post(
        "/api/v1/public/applications",
        json=public_application_payload(client_application_id="public-denied-token"),
    )

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
