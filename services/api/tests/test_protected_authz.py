from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import (
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


pytestmark = pytest.mark.asyncio


@dataclass
class FakeCedarAuthorizer:
    decision: str = "Allow"
    error: Exception | None = None
    requests: list[CedarAuthorizationRequest] = field(default_factory=list)

    def is_authorized(self, request: CedarAuthorizationRequest):
        self.requests.append(request)
        if self.error is not None:
            raise self.error

        return CedarAuthorizationDecision(decision=self.decision)


async def test_protected_authz_allows_pomerium_identity(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    authorizer = FakeCedarAuthorizer()
    app.state.cedar_authorizer = authorizer

    response = await async_client.get(
        "/api/v1/protected/authz-proof",
        headers={"x-pomerium-claim-email": "sample@local.humility.local"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "subject": "sample@local.humility.local",
        "action": 'Action::"api:read"',
        "resource": 'Resource::"server-manager-api"',
        "decision": "Allow",
    }
    assert authorizer.requests == [
        CedarAuthorizationRequest(
            principal='User::"sample@local.humility.local"',
            action='Action::"api:read"',
            resource='Resource::"server-manager-api"',
        )
    ]


async def test_protected_authz_rejects_missing_identity(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    app.state.cedar_authorizer = FakeCedarAuthorizer(
        error=AssertionError("authorizer should not be called without identity")
    )

    response = await async_client.get("/api/v1/protected/authz-proof")

    assert response.status_code == 401
    assert response.json()["code"] == "identity_missing"


async def test_protected_authz_rejects_cedar_deny(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    app.state.cedar_authorizer = FakeCedarAuthorizer(decision="Deny")

    response = await async_client.get(
        "/api/v1/protected/authz-proof",
        headers={"x-pomerium-claim-email": "other@local.humility.local"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "cedar_denied"


async def test_protected_authz_reports_cedar_unavailable(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    app.state.cedar_authorizer = FakeCedarAuthorizer(
        error=CedarAuthorizationUnavailableError("connection refused")
    )

    response = await async_client.get(
        "/api/v1/protected/authz-proof",
        headers={"x-pomerium-claim-email": "sample@local.humility.local"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "cedar_unavailable"
