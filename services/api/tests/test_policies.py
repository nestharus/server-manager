"""SLICE-010 WU-017 — Policy preview/confirm/current HTTP surface."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.policies import PolicyPreviewRead, PolicyVersionRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


PREVIEW_URL = "/api/v1/policies/preview"
CONFIRM_URL = "/api/v1/policies/confirm"
CURRENT_URL = "/api/v1/policies/{policy_type}/current"


def _actor_headers(
    *,
    actor_id: str = "admin",
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


def _expected_aggregate_id(
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
) -> str:
    return f"{policy_type}|{scope_kind}|{scope_id if scope_id is not None else ''}"


def _seed_policy_version(
    database_url: str,
    *,
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
    version_number: int,
    content: dict[str, Any],
) -> UUID:
    row_id = uuid4()
    aggregate_id = _expected_aggregate_id(policy_type, scope_kind, scope_id)
    effective_at = datetime.now(UTC)

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO policy_versions (
                id, policy_type, scope_kind, scope_id,
                version_number, content, effective_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                row_id,
                policy_type,
                scope_kind,
                scope_id,
                version_number,
                json.dumps(content),
                effective_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type, aggregate_id, current_seq, latest_change_id
            )
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (aggregate_type, aggregate_id)
            DO UPDATE SET current_seq = EXCLUDED.current_seq
            """,
            ("policy_version", aggregate_id, version_number),
        )

    return row_id


def _fetch_policy_versions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, policy_type, scope_kind, scope_id,
                   version_number, content, effective_at
            FROM policy_versions
            ORDER BY version_number ASC, effective_at ASC, id ASC
            """
        ).fetchall()


def _fetch_policy_actions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, action_type, aggregate_id, actor_kind, actor_id, status
            FROM activity_actions
            WHERE aggregate_type = 'policy_version'
            ORDER BY id ASC
            """
        ).fetchall()


def _grant_permission(
    db: PostgresDatabase,
    actor_id: str,
    permission: str,
    scope_kind: str = "global",
) -> None:
    with use_audit_context(_make_audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=None,
            permissions=frozenset({permission}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "root"),
        )


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest_asyncio.fixture()
async def policy_client(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001 - forces governance reset
) -> AsyncClient:
    return migrated_async_client


@pytest.mark.asyncio
async def test_preview_requires_policy_write_permission(
    policy_client: AsyncClient,
) -> None:
    response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_preview_returns_preview_read_with_token(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    preview = PolicyPreviewRead.model_validate(response.json())
    assert preview.current_version == 0
    assert preview.preview_token != ""
    assert preview.affected_objects == [{"key": "rules"}]
    assert preview.rollback_summary == {}


@pytest.mark.asyncio
async def test_preview_does_not_mutate_policy_state(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=2,
        content={"rules": ["one"]},
    )
    before = _fetch_policy_versions(governance_dsn)

    response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 2,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert _fetch_policy_versions(governance_dsn) == before


@pytest.mark.asyncio
async def test_confirm_requires_policy_write_permission(
    policy_client: AsyncClient,
) -> None:
    response = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": "deadbeef",
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_confirm_persists_exactly_one_new_version_with_matching_expected_version(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"rules": ["one"]},
    )
    preview_response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 1,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )
    preview = PolicyPreviewRead.model_validate(preview_response.json())
    before = _fetch_policy_versions(governance_dsn)

    confirm_response = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": preview.preview_token,
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 1,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )

    assert confirm_response.status_code == HTTPStatus.CREATED, confirm_response.text
    after = _fetch_policy_versions(governance_dsn)
    assert len(after) == len(before) + 1
    assert after[-1]["version_number"] == 2


@pytest.mark.asyncio
async def test_confirm_returns_policy_version_read_with_etag(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    preview_response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )
    preview = PolicyPreviewRead.model_validate(preview_response.json())

    response = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": preview.preview_token,
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    created = PolicyVersionRead.model_validate(response.json())
    assert created.version_number == 1
    assert response.headers["etag"] == '"1"'


@pytest.mark.asyncio
async def test_confirm_superseded_preview_returns_412(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"rules": ["one"]},
    )
    preview_response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 1,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )
    preview = PolicyPreviewRead.model_validate(preview_response.json())

    first_confirm = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": preview.preview_token,
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 1,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )
    assert first_confirm.status_code == HTTPStatus.CREATED, first_confirm.text

    stale_confirm = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": preview.preview_token,
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 1,
            "content": {"rules": ["two"]},
        },
        headers=_actor_headers(),
    )

    assert stale_confirm.status_code == HTTPStatus.PRECONDITION_FAILED, stale_confirm.text
    body = stale_confirm.json()
    assert body["code"] == "stale_policy_version"
    assert body["expected_current_version"] == 1
    assert body["actual_current_version"] == 2


@pytest.mark.asyncio
async def test_confirm_mismatched_token_returns_412(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    response = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": "deadbeef",
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED, response.text
    body = response.json()
    assert body["code"] == "policy_preview_token_mismatch"
    assert body["expected_current_version"] is None
    assert body["actual_current_version"] is None


@pytest.mark.asyncio
async def test_confirm_records_real_actor_in_audit_row(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.write")
    preview_response = await policy_client.post(
        PREVIEW_URL,
        json={
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(actor_id="admin"),
    )
    preview = PolicyPreviewRead.model_validate(preview_response.json())

    response = await policy_client.post(
        CONFIRM_URL,
        json={
            "preview_token": preview.preview_token,
            "policy_type": "access",
            "scope_kind": "global",
            "scope_id": None,
            "expected_current_version": 0,
            "content": {"rules": ["one"]},
        },
        headers=_actor_headers(actor_id="admin"),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    actions = _fetch_policy_actions(governance_dsn)
    accepted_confirms = [
        action
        for action in actions
        if action["action_type"] == "policy.confirm" and action["status"] == "accepted"
    ]
    assert len(accepted_confirms) == 1
    assert accepted_confirms[0]["actor_kind"] == "user"
    assert accepted_confirms[0]["actor_id"] == "admin"


@pytest.mark.asyncio
async def test_current_requires_policy_read_permission(
    policy_client: AsyncClient,
    governance_dsn: str,
) -> None:
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"rules": ["one"]},
    )

    response = await policy_client.get(
        CURRENT_URL.format(policy_type="access"),
        params={"scope_kind": "global"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_current_returns_latest_policy_version(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.read")
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"rules": ["one"]},
    )
    expected_id = _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=2,
        content={"rules": ["two"]},
    )

    response = await policy_client.get(
        CURRENT_URL.format(policy_type="access"),
        params={"scope_kind": "global"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    current = PolicyVersionRead.model_validate(response.json())
    assert current.id == expected_id
    assert current.version_number == 2
    assert response.headers["etag"] == '"2"'


@pytest.mark.asyncio
async def test_current_returns_404_when_no_policy_exists(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant_permission(governance_db, "admin", "policy.read")
    response = await policy_client.get(
        CURRENT_URL.format(policy_type="missing"),
        params={"scope_kind": "global"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
    assert response.json()["code"] == "policy_version_not_found"


@pytest.mark.asyncio
async def test_current_filters_by_policy_type_and_scope(
    policy_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _grant_permission(governance_db, "admin", "policy.read")
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"rules": ["global"]},
    )
    _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="chapter",
        scope_id="ch-2",
        version_number=3,
        content={"rules": ["other-scope"]},
    )
    _seed_policy_version(
        governance_dsn,
        policy_type="moderation",
        scope_kind="chapter",
        scope_id="ch-1",
        version_number=4,
        content={"rules": ["other-type"]},
    )
    expected_id = _seed_policy_version(
        governance_dsn,
        policy_type="access",
        scope_kind="chapter",
        scope_id="ch-1",
        version_number=2,
        content={"rules": ["target"]},
    )

    response = await policy_client.get(
        CURRENT_URL.format(policy_type="access"),
        params={"scope_kind": "chapter", "scope_id": "ch-1"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    current = PolicyVersionRead.model_validate(response.json())
    assert current.id == expected_id
    assert current.policy_type == "access"
    assert current.scope_kind == "chapter"
    assert current.scope_id == "ch-1"
    assert current.version_number == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        (
            "post",
            PREVIEW_URL,
            {
                "json": {
                    "policy_type": "access",
                    "scope_kind": "global",
                    "scope_id": None,
                    "expected_current_version": 0,
                    "content": {"rules": ["one"]},
                }
            },
        ),
        (
            "post",
            CONFIRM_URL,
            {
                "json": {
                    "preview_token": "deadbeef",
                    "policy_type": "access",
                    "scope_kind": "global",
                    "scope_id": None,
                    "expected_current_version": 0,
                    "content": {"rules": ["one"]},
                }
            },
        ),
        (
            "get",
            CURRENT_URL.format(policy_type="access"),
            {"params": {"scope_kind": "global"}},
        ),
    ],
)
async def test_endpoints_require_actor_identity_header(
    policy_client: AsyncClient,
    method: str,
    url: str,
    kwargs: dict[str, Any],
) -> None:
    response = await getattr(policy_client, method)(url, **kwargs)

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert response.json()["code"] == "actor_identity_missing"
