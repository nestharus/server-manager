"""WU-015B — Override audit policy (AC4).

The override mechanism lives inside ``RequireAuthority(...)``: a denied
decision may be overridden when the actor holds a ``global``-scope grant
for the same permission AND provides a non-empty ``X-Override-Reason``
header. Successful overrides must emit a distinct audit row with
``action_type="authority.override"`` under the active correlation id.

These tests drive the guard via a test-only endpoint and assert on the
resulting ``activity_actions`` rows directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends, FastAPI
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import AuthorityDecisionRead
from app.core.context import use_audit_context
from app.core.dependencies import RequireAuthority
from app.core.factory import create_api_app
from app.core.settings import Settings
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


OVERRIDE_ACTION_TYPE = "authority.override"
TEST_ROUTE_CHAPTER = "/_test/override/chapters/{chapter_id}/manage"
TEST_ROUTE_CHAPTER_CALL = "/_test/override/chapters/{chapter_id}/manage"


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


def _build_router() -> APIRouter:
    router = APIRouter()

    @router.post(TEST_ROUTE_CHAPTER)
    async def guarded(
        chapter_id: str,  # noqa: ARG001 — RequireAuthority resolves from path
        decision: AuthorityDecisionRead = Depends(
            RequireAuthority(
                permission="chapter.write",
                scope_kind="chapter",
                scope_id_param="chapter_id",
            )
        ),
    ) -> dict[str, Any]:
        return decision.model_dump(mode="json")

    return router


@pytest_asyncio.fixture()
async def override_client(
    test_settings: Settings,
    migrated_postgres_db: str,
    governance_dsn: str,  # noqa: ARG001 — truncates governance state
) -> AsyncIterator[tuple[httpx.AsyncClient, PostgresDatabase, str]]:
    app: FastAPI = create_api_app(settings=test_settings)
    app.include_router(_build_router())

    db: PostgresDatabase = app.state.container.core.db()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client, db, migrated_postgres_db


def _seed_grant(
    db: PostgresDatabase,
    *,
    grantee_id: str = "grantee-1",
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
    permissions: frozenset[str] = frozenset({"chapter.write"}),
) -> Any:
    with use_audit_context(_make_audit_context()):
        return grant_authority(
            db=db,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _fetch_override_actions(dsn: str) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, action_type, aggregate_type, aggregate_id,
                   actor_kind, actor_id, status, correlation_id,
                   causation_id, scope_kind, scope_id, request_surface,
                   reason_text, request_json
            FROM activity_actions
            WHERE action_type = %s
            ORDER BY id
            """,
            (OVERRIDE_ACTION_TYPE,),
        ).fetchall()


# ---------------------------------------------------------------------------
# Validation of X-Override-Reason input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_requires_non_empty_reason(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """F6: blank-after-trim override header is equivalent to no override
    attempt; underlying denial still applies."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": "   "},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    # No override audit row was written because no override path was entered.
    assert _fetch_override_actions(dsn) == []


@pytest.mark.asyncio
async def test_override_too_long_rejected(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """F6: an override reason >512 characters (after trim) is rejected 400."""

    client, db, _ = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )
    too_long = "x" * 513

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": too_long},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


# ---------------------------------------------------------------------------
# Successful overrides
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_used_records_distinct_audit_event(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """AC4: an actor with a global-scope grant can override a scope-mismatched
    requirement by supplying ``X-Override-Reason``. The override emits a
    distinct ``activity_actions`` row with ``action_type="authority.override"``
    and the response's ``AuthorityDecisionRead.override_used`` is True."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": "emergency"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["allowed"] is True
    assert body["override_used"] is True

    rows = _fetch_override_actions(dsn)
    assert len(rows) == 1
    assert rows[0]["action_type"] == OVERRIDE_ACTION_TYPE
    assert rows[0]["aggregate_type"] == "authority_override"
    assert rows[0]["status"] == "accepted"


@pytest.mark.asyncio
async def test_override_records_correlation_id(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """AC4: the override audit row carries the request's correlation id."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )

    correlation_id = uuid4()
    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={
            **_actor_headers(),
            "X-Override-Reason": "emergency",
            "X-Correlation-Id": str(correlation_id),
        },
    )

    assert response.status_code == HTTPStatus.OK, response.text

    rows = _fetch_override_actions(dsn)
    assert len(rows) == 1
    assert UUID(str(rows[0]["correlation_id"])) == correlation_id


@pytest.mark.asyncio
async def test_override_records_reason_text(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """AC4: the override audit payload captures the supplied reason verbatim
    (either as ``reason_text`` or inside the request payload)."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )

    reason = "emergency cleanup; see ticket OPS-1234"
    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": reason},
    )

    assert response.status_code == HTTPStatus.OK, response.text

    rows = _fetch_override_actions(dsn)
    assert len(rows) == 1
    row = rows[0]
    # Reason lives either in reason_text or inside the typed request payload,
    # but it must be persisted verbatim somewhere on the audit row.
    reason_text = row["reason_text"]
    payload_blob = row["request_json"]
    payload_str = "" if payload_blob is None else str(payload_blob)
    assert reason_text == reason or reason in payload_str


# ---------------------------------------------------------------------------
# Override is scoped — no global grant means no override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_without_global_grant_denied(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """An actor with only a chapter-scoped grant cannot use ``X-Override-Reason``
    to bypass scope enforcement — the override path requires a global-scope
    grant with the same permission."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="chapter",
        scope_id="ch-X",
        permissions=frozenset({"chapter.write"}),
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": "emergency"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    # No override audit row was written — the override was rejected.
    assert _fetch_override_actions(dsn) == []


# ---------------------------------------------------------------------------
# Aggregate identity uniqueness per override event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_aggregate_id_includes_timestamp(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """F5: aggregate_id for override audit must encode a per-event timestamp
    so repeated overrides under the same correlation_id and permission are
    separate aggregates (no collision on ``aggregate_heads``)."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"chapter.write"}),
    )

    correlation_id = uuid4()
    headers = {
        **_actor_headers(),
        "X-Override-Reason": "emergency",
        "X-Correlation-Id": str(correlation_id),
    }

    first = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"), headers=headers
    )
    second = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"), headers=headers
    )

    assert first.status_code == HTTPStatus.OK, first.text
    assert second.status_code == HTTPStatus.OK, second.text

    rows = _fetch_override_actions(dsn)
    assert len(rows) == 2
    aggregate_ids = {row["aggregate_id"] for row in rows}
    # Distinct aggregate ids prove the timestamp suffix (F5) split the event
    # stream — otherwise the second write would collide on aggregate_heads.
    assert len(aggregate_ids) == 2


# ---------------------------------------------------------------------------
# Override is only meaningful on denial
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_blocked_when_no_denial_to_override(
    override_client: tuple[httpx.AsyncClient, PostgresDatabase, str],
) -> None:
    """If the actor already has a matching grant, presenting
    ``X-Override-Reason`` is a no-op: the endpoint succeeds normally and no
    override audit is emitted."""

    client, db, dsn = override_client
    _seed_grant(
        db,
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=frozenset({"chapter.write"}),
    )

    response = await client.post(
        TEST_ROUTE_CHAPTER_CALL.format(chapter_id="ch-1"),
        headers={**_actor_headers(), "X-Override-Reason": "would-be-emergency"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["allowed"] is True
    assert body["override_used"] is False

    # No override audit row because the underlying decision was already allow.
    assert _fetch_override_actions(dsn) == []
