from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from .authority_slice_helpers import (
    actor_headers,
    create_member,
    grant_permission,
    seed_lifecycle_permissions,
)


BASE_URL = "/api/v1/authority-grants"

LEADER_2_ID = "22222222-2222-2222-2222-222222222222"
LEADER_3_ID = "33333333-3333-3333-3333-333333333333"


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
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    transfer = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert transfer.status_code == HTTPStatus.CREATED, transfer.text
    body = transfer.json()
    assert body["grantee_id"] == LEADER_2_ID
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
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    first = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )
    assert first.status_code == HTTPStatus.CREATED, first.text

    replay = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
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
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    first = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )
    assert first.status_code == HTTPStatus.CREATED, first.text

    replay = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_3_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert replay.status_code == HTTPStatus.CONFLICT, replay.text
    assert replay.json()["code"] == "grant_already_transferred"
    assert replay.json()["existing_grant_id"] == first.json()["id"]


# ---------------------------------------------------------------------------
# CodeRabbit MAJOR 1-3
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transfer_etag_matches_successor_version(
    migrated_async_client: AsyncClient,
    governance_db: object,
    governance_dsn: str,
) -> None:
    """MAJOR 1: response ETag reflects the successor grant the body describes.

    The transfer endpoint previously re-read the grant after the transaction
    committed to compute the ETag, so the body and ETag could disagree if a
    concurrent write mutated the row in between. The ETag now comes from the
    same transactional read as the body.
    """

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    transfer = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )
    assert transfer.status_code == HTTPStatus.CREATED, transfer.text
    successor_id = transfer.json()["id"]
    successor_etag = transfer.headers["etag"]

    with psycopg.connect(governance_dsn, row_factory=dict_row) as connection:
        head = connection.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'authority_grant' AND aggregate_id = %s
            """,
            (successor_id,),
        ).fetchone()
    assert head is not None
    assert successor_etag == f'"{head["current_seq"]}"'


@pytest.mark.asyncio
async def test_transfer_rejects_invalid_successor_id(
    migrated_async_client: AsyncClient,
    governance_db: object,
) -> None:
    """MAJOR 3: successor_id must be a UUID or Discord ID.

    Previously any non-blank string was accepted, so a malformed id silently
    stranded the transferred grant. Validation now mirrors other holder-id
    fields (R5).
    """

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    response = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": "not-a-valid-id", "reason": "succession"},
        headers={
            **actor_headers(actor_id="operator"),
            "If-Match": created.headers["etag"],
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_holder_id"


@pytest.mark.asyncio
async def test_transfer_authorization_resolves_member_aliases(
    migrated_async_client: AsyncClient,
    governance_db: object,
) -> None:
    """MAJOR 2: actor authenticating with Discord ID satisfies a grant stored under member UUID.

    ``_require_scoped_authority`` now merges grants across the actor's
    canonical member UUID and Discord ID aliases, so either identifier can
    unlock a permission regardless of which alias the grant was written
    under.
    """

    operator_discord_id = "987654321098765432"
    operator_member_uuid = create_member(
        governance_db, discord_user_id=operator_discord_id
    )
    grant_permission(
        governance_db,
        actor_id=operator_member_uuid,
        permission="authority_grant.transfer",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    seed_lifecycle_permissions(governance_db, actor_id="admin")
    created = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="leader-1"),
        headers=actor_headers(actor_id="admin"),
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    transfer = await migrated_async_client.post(
        f"{BASE_URL}/{created.json()['id']}/transfer",
        json={"successor_id": LEADER_2_ID, "reason": "succession"},
        headers={
            **actor_headers(actor_id=operator_discord_id),
            "If-Match": created.headers["etag"],
        },
    )

    assert transfer.status_code == HTTPStatus.CREATED, transfer.text
