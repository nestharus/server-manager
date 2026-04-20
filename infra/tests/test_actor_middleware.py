"""ActorMiddleware — request-header actor identity substrate.

These tests pin the SLICE-008 D1 middleware contract:

- ``X-Actor-Kind`` must be one of ``user | service | system``.
- ``X-Actor-Id`` is opaque but must be a non-empty string.
- Missing or invalid headers -> 401 with typed ``actor_identity_missing`` body.
- Valid headers populate the ``CURRENT_ACTOR`` ``ContextVar`` for endpoint
  code to observe.
- The 401 emitted by middleware must still carry ``X-Correlation-Id``
  because ``CorrelationMiddleware`` is registered outermost (F3).
- Actor context is request-scoped: a subsequent request without headers
  must not inherit the prior actor from the process-global ``ContextVar``.

Tests run against a full ASGI app built by ``create_api_app`` via the
shared ``infra/tests`` fixture stack.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio


_API_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "api"
if str(_API_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(_API_SERVICE_PATH))

from fastapi import APIRouter, FastAPI  # noqa: E402

from app.contracts.actor import ActorIdentity  # noqa: E402
from app.core.context import CURRENT_ACTOR, get_current_actor  # noqa: E402
from app.core.factory import create_api_app  # noqa: E402


ACTOR_PROBE_ROUTE = "/_test/actor-probe"


def _build_probe_router() -> APIRouter:
    router = APIRouter()

    @router.get(ACTOR_PROBE_ROUTE)
    async def probe() -> dict[str, Any]:
        current = get_current_actor()
        return {
            "actor_kind": current.actor_kind,
            "actor_id": current.actor_id,
        }

    return router


@pytest_asyncio.fixture()
async def probed_client(
    test_settings: Any,
    migrated_postgres_db: str,  # noqa: ARG001 — forces migrations before requests
) -> AsyncIterator[httpx.AsyncClient]:
    app: FastAPI = create_api_app(settings=test_settings)
    app.include_router(_build_probe_router())

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client


def _actor_headers(
    *,
    actor_kind: str | None = "user",
    actor_id: str | None = "test-user",
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if actor_kind is not None:
        headers["X-Actor-Kind"] = actor_kind
    if actor_id is not None:
        headers["X-Actor-Id"] = actor_id
    return headers


# ---------------------------------------------------------------------------
# Missing / invalid actor headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_actor_kind_header_returns_401(
    probed_client: httpx.AsyncClient,
) -> None:
    """``X-Actor-Id`` alone is not enough; the body names the missing header."""

    response = await probed_client.get(
        "/api/v1/health",
        headers=_actor_headers(actor_kind=None),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    body = response.json()
    assert body["code"] == "actor_identity_missing"
    message = str(body)
    assert "X-Actor-Kind" in message or "actor_kind" in message


@pytest.mark.asyncio
async def test_missing_actor_id_header_returns_401(
    probed_client: httpx.AsyncClient,
) -> None:
    """``X-Actor-Kind`` alone is not enough; the body names the missing header."""

    response = await probed_client.get(
        "/api/v1/health",
        headers=_actor_headers(actor_id=None),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    body = response.json()
    assert body["code"] == "actor_identity_missing"
    message = str(body)
    assert "X-Actor-Id" in message or "actor_id" in message


@pytest.mark.asyncio
async def test_invalid_actor_kind_returns_401(
    probed_client: httpx.AsyncClient,
) -> None:
    """``X-Actor-Kind`` is constrained to ``user | service | system``; any
    other value is rejected as a malformed identity."""

    response = await probed_client.get(
        "/api/v1/health",
        headers=_actor_headers(actor_kind="root"),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert response.json()["code"] == "actor_identity_missing"


# ---------------------------------------------------------------------------
# Valid headers populate the request-scope ContextVar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_actor_headers_set_current_actor_contextvar(
    probed_client: httpx.AsyncClient,
) -> None:
    """With valid headers, endpoint code reading ``CURRENT_ACTOR`` receives a
    parsed ``ActorIdentity`` matching the headers."""

    response = await probed_client.get(
        ACTOR_PROBE_ROUTE,
        headers=_actor_headers(actor_kind="service", actor_id="scheduler-7"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    identity = ActorIdentity(actor_kind=body["actor_kind"], actor_id=body["actor_id"])
    assert identity.actor_kind == "service"
    assert identity.actor_id == "scheduler-7"


# ---------------------------------------------------------------------------
# 401 still gets correlation header (F3 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_401_response_includes_correlation_header(
    probed_client: httpx.AsyncClient,
) -> None:
    """F3: ``CorrelationMiddleware`` is registered outside ``ActorMiddleware``
    so a 401 from missing actor headers still emits ``X-Correlation-Id``."""

    response = await probed_client.get("/api/v1/health")

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    correlation = response.headers.get("x-correlation-id")
    assert correlation is not None, (
        "401 responses from ActorMiddleware must still carry X-Correlation-Id"
    )


# ---------------------------------------------------------------------------
# Request-scoped context teardown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actor_context_cleared_after_response(
    probed_client: httpx.AsyncClient,
) -> None:
    """A subsequent request without actor headers must not inherit the prior
    request's actor from the process-global ``CURRENT_ACTOR`` ``ContextVar``.

    If the middleware did not reset the contextvar, the second request would
    observe the first actor and succeed — the 401 here proves cleanup.
    """

    # Baseline: no actor set before any request.
    assert CURRENT_ACTOR.get() is None

    first = await probed_client.get(
        ACTOR_PROBE_ROUTE,
        headers=_actor_headers(actor_kind="user", actor_id="alice"),
    )
    assert first.status_code == HTTPStatus.OK, first.text

    second = await probed_client.get(ACTOR_PROBE_ROUTE)
    assert second.status_code == HTTPStatus.UNAUTHORIZED, second.text

    # Context is still None from the test's perspective: the middleware must
    # not have leaked actor state back to the caller's context.
    assert CURRENT_ACTOR.get() is None
