from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from .authority_slice_helpers import actor_headers, grant_permission


BASE_URL = "/api/v1/authority-grants"


def _create_payload(*, grantee_id: str, scope_id: str = "chapter-1") -> dict[str, object]:
    return {
        "grantee_id": grantee_id,
        "scope_kind": "chapter",
        "scope_id": scope_id,
        "permissions": ["chapter.write"],
    }


def _grant_rows(dsn: str) -> list[dict[str, object]]:
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        return connection.execute(
            """
            SELECT id, grantee_id, revoked_at, predecessor_grant_id
            FROM authority_grants
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()


@pytest.mark.asyncio
async def test_transfer_creates_successor_and_revokes_predecessor(
    migrated_async_client: AsyncClient,
    governance_db: object,
    governance_dsn: str,
) -> None:
    """AC2: transfer creates a linked successor grant and revokes the predecessor."""

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    transfer = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "leader-2", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert transfer.status_code == HTTPStatus.CREATED, transfer.text
    body = transfer.json()
    assert body["grantee_id"] == "leader-2"
    assert body["predecessor_grant_id"] == created.json()["id"]

    rows = _grant_rows(governance_dsn)
    predecessor = next(row for row in rows if str(row["id"]) == created.json()["id"])
    assert predecessor["revoked_at"] is not None


@pytest.mark.asyncio
async def test_transfer_replay_with_same_successor_returns_existing_successor(
    migrated_async_client: AsyncClient,
    governance_db: object,
) -> None:
    """AC2: replaying the same successor returns 200 with the existing successor grant."""

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    first = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "leader-2", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )
    assert first.status_code == HTTPStatus.CREATED, first.text

    replay = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "leader-2", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert replay.status_code == HTTPStatus.OK, replay.text
    assert replay.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_transfer_replay_with_different_successor_conflicts(
    migrated_async_client: AsyncClient,
    governance_db: object,
) -> None:
    """AC2: replaying with a different successor returns 409 for the existing transfer."""

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    first = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "leader-2", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )
    assert first.status_code == HTTPStatus.CREATED, first.text

    replay = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "leader-3", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert replay.status_code == HTTPStatus.CONFLICT, replay.text
    assert replay.json()["code"] == "grant_already_transferred"
    assert replay.json()["existing_grant_id"] == first.json()["id"]
