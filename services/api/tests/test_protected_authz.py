from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from httpx import AsyncClient

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import (
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


pytestmark = pytest.mark.asyncio
REPO_ROOT = Path(__file__).resolve().parents[3]
AUTH_STACK_FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "auth_stack_contract.yml"
)


def _contract() -> dict:
    return yaml.safe_load(AUTH_STACK_FIXTURE.read_text(encoding="utf-8"))


def _case(name: str) -> dict:
    return next(case for case in _contract()["api_proof_cases"] if case["name"] == name)


def _request_payload(request: CedarAuthorizationRequest) -> dict[str, str]:
    return {
        "principal": request.principal,
        "action": request.action,
        "resource": request.resource,
    }


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
    override_provider,
) -> None:
    case = _case("allowed_identity")
    authorizer = FakeCedarAuthorizer(decision=case["cedar_decision"])

    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        response = await async_client.get(
            "/api/v1/protected/authz-proof",
            headers=case["headers"],
        )

    assert response.status_code == case["expected_status"]
    assert response.json() == case["expected_response"]
    assert [_request_payload(request) for request in authorizer.requests] == [
        case["expected_request"]
    ]


async def test_protected_authz_rejects_missing_identity(
    app: FastAPI,
    async_client: AsyncClient,
    override_provider,
) -> None:
    case = _case("missing_identity")
    authorizer = FakeCedarAuthorizer(
        error=AssertionError("authorizer should not be called without identity")
    )

    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        response = await async_client.get("/api/v1/protected/authz-proof")

    assert response.status_code == case["expected_status"]
    assert response.json()["code"] == case["expected_error_code"]


async def test_protected_authz_rejects_cedar_deny(
    app: FastAPI,
    async_client: AsyncClient,
    override_provider,
) -> None:
    case = _case("denied_identity")
    authorizer = FakeCedarAuthorizer(decision=case["cedar_decision"])

    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        response = await async_client.get(
            "/api/v1/protected/authz-proof",
            headers=case["headers"],
        )

    assert response.status_code == case["expected_status"]
    assert response.json()["code"] == case["expected_error_code"]
    assert [_request_payload(request) for request in authorizer.requests] == [
        case["expected_request"]
    ]


async def test_protected_authz_reports_cedar_unavailable(
    app: FastAPI,
    async_client: AsyncClient,
    override_provider,
) -> None:
    case = _case("policy_engine_unavailable")
    authorizer = FakeCedarAuthorizer(
        error=CedarAuthorizationUnavailableError("connection refused")
    )

    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        response = await async_client.get(
            "/api/v1/protected/authz-proof",
            headers=case["headers"],
        )

    assert response.status_code == case["expected_status"]
    assert response.json()["code"] == case["expected_error_code"]
    assert [_request_payload(request) for request in authorizer.requests] == [
        case["expected_request"]
    ]
