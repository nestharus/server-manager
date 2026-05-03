"""WU-015A — Authority enforcement guard (AC3).

Mounts a test-only route behind ``RequireAuthority(...)`` and exercises
the full decision surface: the actor middleware, the scope/permission
evaluator, and the denial-reason priority order pinned by the proposal.

The guarded endpoints return the raw ``AuthorityDecisionRead`` so tests
can observe ``allowed``, ``grant_id``, ``denial_reason``, and
``override_used`` directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends, FastAPI

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import AuthorityDecisionRead, AuthorityRequirement
from app.core.context import use_audit_context
from app.core.dependencies import RequireAuthority
from app.core.factory import create_api_app
from app.core.settings import Settings
from app.repositories.db import PostgresDatabase
from app.services.authority import (
    current_time,
    evaluate,
)
from tests._authority_helpers import grant_authority, revoke_authority


TEST_ROUTE_CHAPTER = "/_test/authority/chapters/{chapter_id}/manage"
TEST_ROUTE_CHAPTER_CALL = "/_test/authority/chapters/{chapter_id}/manage"
TEST_ROUTE_GLOBAL = "/_test/authority/global/ping"


def _actor_headers(
    *,
    actor_id: str = "grantee-1",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=None,
        headers=CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None),
    )


def _build_test_router() -> APIRouter:
    router = APIRouter()

    @router.post(TEST_ROUTE_CHAPTER)
    async def guarded_chapter_manage(
        chapter_id: str,  # noqa: ARG001 — path param used by RequireAuthority
        decision: AuthorityDecisionRead = Depends(
            RequireAuthority(
                permission="chapter.write",
                scope_kind="chapter",
                scope_id_param="chapter_id",
            )
        ),
    ) -> dict[str, Any]:
        return decision.model_dump(mode="json")

    @router.post(TEST_ROUTE_GLOBAL)
    async def guarded_global(
        decision: AuthorityDecisionRead = Depends(
            RequireAuthority(
                permission="system.manage",
                scope_kind="global",
                scope_id_param=None,
            )
        ),
    ) -> dict[str, Any]:
        return decision.model_dump(mode="json")

    return router


@pytest_asyncio.fixture()
async def guarded_client(
    test_settings: Settings,
    migrated_postgres_db: str,
    governance_dsn: str,  # noqa: ARG001 — truncates governance state
) -> AsyncIterator[tuple[httpx.AsyncClient, PostgresDatabase]]:
    app: FastAPI = create_api_app(settings=test_settings)
    app.include_router(_build_test_router())

    db: PostgresDatabase = app.state.container.core.db()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client, db


def _seed_grant(
    db: PostgresDatabase,
    *,
    grantee_id: str = "grantee-1",
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
    permissions: frozenset[str] = frozenset({"chapter.write"}),
    expires_at: datetime | None = None,
) -> Any:
    with use_audit_context(_make_audit_context()):
        return grant_authority(
            db=db,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=expires_at,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


# ---------------------------------------------------------------------------
# Allow / deny golden paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guarded_surface_returns_403_without_grant(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """AC3: an actor with zero grants gets 403 + ``no_matching_grant``."""

    client, _ = guarded_client

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    body = response.json()
    assert body["code"] == "authority_decision_denied"
    assert body["decision"]["allowed"] is False
    assert body["decision"]["denial_reason"] == "no_matching_grant"


@pytest.mark.asyncio
async def test_guarded_surface_allows_when_grant_covers_requirement(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """AC3: a matching grant yields 200 + ``AuthorityDecisionRead.allowed=True``
    with ``grant_id`` populated."""

    client, db = guarded_client
    result = _seed_grant(
        db,
        grantee_id="grantee-1",
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=frozenset({"chapter.write"}),
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["allowed"] is True
    assert body["grant_id"] == str(result.id)
    assert body["override_used"] is False


# ---------------------------------------------------------------------------
# Denial-reason matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_scope_mismatch(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """A grant for chapter X does not authorize actions on chapter Y."""

    client, db = guarded_client
    _seed_grant(db, scope_id="ch-X", permissions=frozenset({"chapter.write"}))

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-Y"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "scope_mismatch"


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_permission_missing(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """A scope-matching grant without the required permission denies with
    ``permission_missing``."""

    client, db = guarded_client
    _seed_grant(db, scope_id="ch-1", permissions=frozenset({"chapter.read"}))

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "permission_missing"


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_grant_expired(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """A would-otherwise-match grant whose ``expires_at`` is in the past
    produces ``grant_expired``."""

    client, db = guarded_client
    past = datetime.now(UTC) - timedelta(hours=1)
    _seed_grant(
        db,
        scope_id="ch-1",
        permissions=frozenset({"chapter.write"}),
        expires_at=past,
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "grant_expired"


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_grant_revoked(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """A would-otherwise-match grant that has been revoked produces
    ``grant_revoked``."""

    client, db = guarded_client
    result = _seed_grant(
        db, scope_id="ch-1", permissions=frozenset({"chapter.write"})
    )
    with use_audit_context(_make_audit_context()):
        revoke_authority(
            db=db,
            grant_id=result.id,
            actor=("user", "admin"),
            revoked_by="admin",
            reason="cleanup",
        )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "grant_revoked"


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_no_matching_grant(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """Grantee with zero rows maps to ``no_matching_grant`` explicitly."""

    client, _ = guarded_client

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(actor_id="brand-new-actor"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "no_matching_grant"


@pytest.mark.asyncio
async def test_guarded_surface_denial_reason_priority_order(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """When multiple grants would trigger different reasons, priority order
    (1 no_matching_grant > 2 scope_mismatch > 3 permission_missing >
    4 grant_expired > 5 grant_revoked) is deterministic.

    Given one expired-but-otherwise-matching grant and one revoked-but-
    otherwise-matching grant, the decision is ``grant_expired`` because
    ``grant_expired`` has higher priority than ``grant_revoked``.
    """

    client, db = guarded_client
    past = datetime.now(UTC) - timedelta(hours=1)
    # Grant A: otherwise-matches, expired -> would emit grant_expired
    _seed_grant(
        db,
        scope_id="ch-1",
        permissions=frozenset({"chapter.write"}),
        expires_at=past,
    )
    # Grant B: otherwise-matches, revoked -> would emit grant_revoked
    revokable = _seed_grant(
        db, scope_id="ch-1", permissions=frozenset({"chapter.write"})
    )
    with use_audit_context(_make_audit_context()):
        revoke_authority(
            db=db,
            grant_id=revokable.id,
            actor=("user", "admin"),
            revoked_by="admin",
            reason="cleanup",
        )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["decision"]["denial_reason"] == "grant_expired"


# ---------------------------------------------------------------------------
# Scope resolution from path params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guarded_surface_resolves_scope_id_from_path_param(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """``scope_id_param="chapter_id"`` pulls the scope_id from the path."""

    client, db = guarded_client
    result = _seed_grant(
        db, scope_id="ch-abc", permissions=frozenset({"chapter.write"})
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-abc"),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["allowed"] is True
    assert body["grant_id"] == str(result.id)


# ---------------------------------------------------------------------------
# Actor identity — middleware behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guarded_surface_no_actor_headers_returns_401(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """Missing actor headers -> 401 + ``actor_identity_missing`` before any
    authority evaluation runs."""

    client, _ = guarded_client

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    body = response.json()
    # ActorMiddleware surfaces the typed body.
    assert body["code"] == "actor_identity_missing"


@pytest.mark.asyncio
async def test_guarded_surface_response_includes_correlation_header(
    guarded_client: tuple[httpx.AsyncClient, PostgresDatabase],
) -> None:
    """F3: CorrelationMiddleware sits outside ActorMiddleware so 401/403
    responses still emit ``X-Correlation-Id``."""

    client, _ = guarded_client

    unauthorized = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
    )
    forbidden = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers=_actor_headers(actor_id="no-grants-for-me"),
    )

    assert unauthorized.status_code == HTTPStatus.UNAUTHORIZED
    assert forbidden.status_code == HTTPStatus.FORBIDDEN
    assert "x-correlation-id" in {k.lower() for k in unauthorized.headers.keys()}
    assert "x-correlation-id" in {k.lower() for k in forbidden.headers.keys()}


# ---------------------------------------------------------------------------
# Pure evaluator surface
# ---------------------------------------------------------------------------


def test_evaluate_returns_authority_decision_read_with_grant_id_on_allow() -> None:
    """``evaluate(...)`` returns the widened ``AuthorityDecisionRead`` and
    populates ``grant_id`` with the specific grant that satisfied the
    requirement."""

    from uuid import uuid4 as _uuid4

    from app.contracts.authority import AuthorityGrantRead

    grant_id = _uuid4()
    grant = AuthorityGrantRead(
        id=grant_id,
        grantee_id="u1",
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=frozenset({"chapter.write"}),
        expires_at=None,
        revoked_at=None,
        predecessor_grant_id=None,
    )
    requirement = AuthorityRequirement(
        scope_kind="chapter", scope_id="ch-1", permission="chapter.write"
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=current_time())

    assert isinstance(decision, AuthorityDecisionRead)
    assert decision.allowed is True
    assert decision.grant_id == grant_id
    assert decision.denial_reason is None
    assert decision.override_used is False
