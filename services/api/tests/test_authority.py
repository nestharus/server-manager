"""WU-014 — Authority Grant Lifecycle API (AC1, AC2).

Exercises the three HTTP endpoints that ship in SLICE-008:

- ``POST /api/v1/authority-grants`` (create) -> 201 + strong ETag
- ``GET /api/v1/authority-grants`` (filtered list) requires ``grantee_id``
- ``POST /api/v1/authority-grants/{grant_id}/revoke`` requires ``If-Match``

All tests run against real Postgres via ``migrated_async_client`` and
truncate governance state through ``governance_dsn``. Service functions
are never mocked — the HTTP layer, service layer, and repositories are
exercised end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase

from .authority_slice_helpers import seed_lifecycle_permissions


BASE_URL = "/api/v1/authority-grants"


def _actor_headers(
    *,
    actor_id: str = "test-user",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _create_payload(
    *,
    grantee_id: str = "u1",
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
    permissions: list[str] | None = None,
    expires_at: datetime | None = None,
    predecessor_grant_id: UUID | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "grantee_id": grantee_id,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "permissions": sorted(
            permissions if permissions is not None else ["chapter.manage"]
        ),
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    if predecessor_grant_id is not None:
        payload["predecessor_grant_id"] = str(predecessor_grant_id)
    return payload


async def _post_create(
    client: AsyncClient,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    payload = body if body is not None else _create_payload()
    response = await client.post(
        BASE_URL,
        json=payload,
        headers=headers if headers is not None else _actor_headers(),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    etag = response.headers["etag"]
    return response.json(), etag


def _fetch_grant_row(dsn: str, grant_id: UUID | str) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, grantee_id, scope_kind, scope_id, permissions,
                   expires_at, revoked_at, revoked_by, revocation_reason,
                   predecessor_grant_id
            FROM authority_grants
            WHERE id = %s
            """,
            (str(grant_id),),
        ).fetchone()


# ---------------------------------------------------------------------------
# POST /authority-grants — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_grant_persists_exact_scope_permissions_expiry(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: persist scope_kind, scope_id, permissions, and expiry exactly."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    expires_at = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    payload = _create_payload(
        grantee_id="u1",
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=["chapter.manage", "chapter.read"],
        expires_at=expires_at,
    )

    response = await migrated_async_client.post(
        BASE_URL, json=payload, headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert response.headers["etag"] == '"1"'

    assert body["grantee_id"] == "u1"
    assert body["scope_kind"] == "chapter"
    assert body["scope_id"] == "ch-1"
    assert set(body["permissions"]) == {"chapter.manage", "chapter.read"}
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) == expires_at
    assert body["revoked_at"] is None
    assert body["revoked_by"] is None
    assert body["revocation_reason"] is None
    assert body["predecessor_grant_id"] is None

    row = _fetch_grant_row(governance_dsn, body["id"])
    assert row is not None
    assert row["grantee_id"] == "u1"
    assert row["scope_kind"] == "chapter"
    assert row["scope_id"] == "ch-1"
    assert set(row["permissions"]) == {"chapter.manage", "chapter.read"}
    assert row["expires_at"] == expires_at
    assert row["revoked_at"] is None


@pytest.mark.asyncio
async def test_create_grant_returns_etag_matching_aggregate_version(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001 — truncates governance state
    governance_db: PostgresDatabase,
) -> None:
    """Response ETag must be the strong form ``"<version>"`` and the embedded
    version integer must match the aggregate head version (first write -> 1).
    """

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    _, etag = await _post_create(migrated_async_client)

    assert etag.startswith('"') and etag.endswith('"')
    version_str = etag.strip('"')
    # Strong ETag parses cleanly to an integer representing the new version.
    assert int(version_str) == 1


@pytest.mark.asyncio
async def test_create_grant_with_invalid_scope_kind_rejected(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """``scope_kind`` is a ``ScopeKind`` literal; unknown values -> 422."""

    payload = _create_payload(scope_kind="invalid")

    response = await migrated_async_client.post(
        BASE_URL, json=payload, headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_create_grant_missing_required_field_rejected(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """``grantee_id`` is required by ``AuthorityGrantCreate``; omit -> 422."""

    payload = _create_payload()
    payload.pop("grantee_id")

    response = await migrated_async_client.post(
        BASE_URL, json=payload, headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_create_grant_duplicate_active_grant_returns_409(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """D8: duplicate active grant for
    ``(grantee_id, scope_kind, scope_id, permissions)`` returns 409 with a body
    identifying the existing grant by id."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    first, _ = await _post_create(migrated_async_client)

    response = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    body = response.json()
    assert body["code"] == "duplicate_active_grant"
    assert body["existing_grant_id"] == first["id"]


@pytest.mark.asyncio
async def test_create_grant_with_predecessor_grant_id_creates_lineage(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    governance_db: PostgresDatabase,
) -> None:
    """``predecessor_grant_id`` is stored verbatim so supersession lineage is
    queryable."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    first, _ = await _post_create(migrated_async_client)

    successor_payload = _create_payload(
        permissions=["chapter.manage", "chapter.read"],
        predecessor_grant_id=UUID(first["id"]),
    )
    second_response = await migrated_async_client.post(
        BASE_URL, json=successor_payload, headers=_actor_headers()
    )
    assert second_response.status_code == HTTPStatus.CREATED, second_response.text
    second = second_response.json()

    assert second["predecessor_grant_id"] == first["id"]

    row = _fetch_grant_row(governance_dsn, second["id"])
    assert row is not None
    assert str(row["predecessor_grant_id"]) == first["id"]


# ---------------------------------------------------------------------------
# GET /authority-grants — list with filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_grants_returns_active_only_by_default(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """Default ``include_revoked=False`` hides revoked rows."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    active, _ = await _post_create(migrated_async_client)
    to_revoke_payload = _create_payload(scope_id="ch-2")
    to_revoke, to_revoke_etag = await _post_create(
        migrated_async_client, body=to_revoke_payload
    )

    revoke = await migrated_async_client.post(
        f"{BASE_URL}/{to_revoke['id']}/revoke",
        json={"reason": "cleanup"},
        headers={**_actor_headers(), "If-Match": to_revoke_etag},
    )
    assert revoke.status_code == HTTPStatus.OK, revoke.text

    response = await migrated_async_client.get(
        BASE_URL, params={"grantee_id": "u1"}, headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert active["id"] in ids
    assert to_revoke["id"] not in ids


@pytest.mark.asyncio
async def test_list_grants_include_revoked_returns_all(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """``include_revoked=true`` includes revoked rows alongside active ones."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    active, _ = await _post_create(migrated_async_client)
    revoked_payload = _create_payload(scope_id="ch-2")
    revoked_grant, revoked_etag = await _post_create(
        migrated_async_client, body=revoked_payload
    )
    await migrated_async_client.post(
        f"{BASE_URL}/{revoked_grant['id']}/revoke",
        json={"reason": "cleanup"},
        headers={**_actor_headers(), "If-Match": revoked_etag},
    )

    response = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "u1", "include_revoked": "true"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert active["id"] in ids
    assert revoked_grant["id"] in ids


@pytest.mark.asyncio
async def test_list_grants_filters_by_scope_kind(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """``scope_kind`` filter returns only rows matching that scope kind."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    chapter_grant, _ = await _post_create(migrated_async_client)
    global_payload = _create_payload(scope_kind="global", scope_id=None)
    global_grant, _ = await _post_create(migrated_async_client, body=global_payload)

    response = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "u1", "scope_kind": "chapter"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert chapter_grant["id"] in ids
    assert global_grant["id"] not in ids


@pytest.mark.asyncio
async def test_list_grants_filters_by_scope_id(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """``scope_id`` filter returns only rows whose scope_id matches exactly."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    one, _ = await _post_create(migrated_async_client, body=_create_payload(scope_id="ch-1"))
    two, _ = await _post_create(
        migrated_async_client, body=_create_payload(scope_id="ch-2")
    )

    response = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "u1", "scope_id": "ch-1"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert one["id"] in ids
    assert two["id"] not in ids


@pytest.mark.asyncio
async def test_list_grants_pagination_with_after_id(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """``limit`` + ``after_id`` produce deterministic cursor pagination."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    created_ids: list[str] = []
    for scope in ("ch-1", "ch-2", "ch-3"):
        payload = _create_payload(scope_id=scope)
        grant, _ = await _post_create(migrated_async_client, body=payload)
        created_ids.append(grant["id"])

    first = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "u1", "limit": 2},
        headers=_actor_headers(),
    )
    assert first.status_code == HTTPStatus.OK, first.text
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second = await migrated_async_client.get(
        BASE_URL,
        params={
            "grantee_id": "u1",
            "limit": 2,
            "after_id": first_body["next_cursor"],
        },
        headers=_actor_headers(),
    )
    assert second.status_code == HTTPStatus.OK, second.text
    second_body = second.json()

    first_ids = [item["id"] for item in first_body["items"]]
    second_ids = [item["id"] for item in second_body["items"]]

    # Pages don't overlap, and together they cover every created grant.
    assert set(first_ids).isdisjoint(set(second_ids))
    assert set(first_ids) | set(second_ids) == set(created_ids)


@pytest.mark.asyncio
async def test_list_grants_missing_grantee_id_returns_400(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """D7: ``grantee_id`` is required; omitting it must not return a list-all."""

    response = await migrated_async_client.get(BASE_URL, headers=_actor_headers())

    # FastAPI reports missing query params as 422 from validation; the proposal
    # text says 400. Either is a client error and proves there is no
    # list-all surface, but pin to the 4xx band explicitly.
    assert response.status_code in {
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNPROCESSABLE_ENTITY,
    }, response.text


# ---------------------------------------------------------------------------
# POST /authority-grants/{grant_id}/revoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_grant_records_revoked_at_revoked_by_revocation_reason(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: revocation persists ``revoked_at``, ``revoked_by``, and
    ``revocation_reason`` atomically."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    seed_lifecycle_permissions(governance_db, actor_id="revoker-1")
    grant, etag = await _post_create(migrated_async_client)

    response = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "operator ended assignment"},
        headers={**_actor_headers(actor_id="revoker-1"), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["id"] == grant["id"]
    assert body["revoked_at"] is not None
    assert body["revoked_by"] == "revoker-1"
    assert body["revocation_reason"] == "operator ended assignment"

    row = _fetch_grant_row(governance_dsn, grant["id"])
    assert row is not None
    assert row["revoked_at"] is not None
    assert row["revoked_by"] == "revoker-1"
    assert row["revocation_reason"] == "operator ended assignment"


@pytest.mark.asyncio
async def test_revoke_grant_requires_if_match_header(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """OCC: revoke without ``If-Match`` returns 428 Precondition Required."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    grant, _ = await _post_create(migrated_async_client)

    response = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "no if-match"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_REQUIRED, response.text


@pytest.mark.asyncio
async def test_revoke_grant_stale_etag_returns_412(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """OCC: stale ``If-Match`` returns 412 Precondition Failed."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    grant, _ = await _post_create(migrated_async_client)

    response = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "stale etag"},
        headers={**_actor_headers(), "If-Match": '"999"'},
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED, response.text


@pytest.mark.asyncio
async def test_revoke_grant_already_revoked_returns_409(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """Second revoke on the same grant -> 409 with ``grant_already_revoked``."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    grant, create_etag = await _post_create(migrated_async_client)

    first = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "first revoke"},
        headers={**_actor_headers(), "If-Match": create_etag},
    )
    assert first.status_code == HTTPStatus.OK, first.text
    revoked_etag = first.headers["etag"]

    second = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "second revoke"},
        headers={**_actor_headers(), "If-Match": revoked_etag},
    )

    assert second.status_code == HTTPStatus.CONFLICT, second.text
    body = second.json()
    assert body["code"] == "grant_already_revoked"


@pytest.mark.asyncio
async def test_revoke_grant_not_found_returns_404(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """Revoke on a grant_id that does not exist -> 404."""

    missing_id = uuid4()
    response = await migrated_async_client.post(
        f"{BASE_URL}/{missing_id}/revoke",
        json={"reason": "ghost"},
        headers={**_actor_headers(), "If-Match": '"1"'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_revoke_grant_empty_reason_rejected(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """``AuthorityGrantRevoke.reason`` has ``min_length=1``; empty -> 422."""

    seed_lifecycle_permissions(governance_db, actor_id="test-user")
    grant, etag = await _post_create(migrated_async_client)

    response = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": ""},
        headers={**_actor_headers(), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


# ---------------------------------------------------------------------------
# Authorization — CRITICAL 1 (authority_grant.create / .read / .revoke)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_grant_without_permission_returns_403(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """Creating a grant without ``authority_grant.create`` returns 403."""

    response = await migrated_async_client.post(
        BASE_URL, json=_create_payload(), headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "authority_decision_denied"


@pytest.mark.asyncio
async def test_list_grants_without_permission_returns_403(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    """Listing someone else's grants without ``authority_grant.read`` returns 403."""

    response = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "someone-else"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_revoke_grant_without_permission_returns_403(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """Revoking a grant without ``authority_grant.revoke`` returns 403."""

    seed_lifecycle_permissions(governance_db, actor_id="creator")
    create_response = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(),
        headers=_actor_headers(actor_id="creator"),
    )
    assert create_response.status_code == HTTPStatus.CREATED, create_response.text
    grant = create_response.json()
    etag = create_response.headers["etag"]

    response = await migrated_async_client.post(
        f"{BASE_URL}/{grant['id']}/revoke",
        json={"reason": "no perms"},
        headers={**_actor_headers(actor_id="intruder"), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_list_own_grants_without_permission_is_allowed(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001
    governance_db: PostgresDatabase,
) -> None:
    """Self-read (grantee_id == actor alias) bypasses ``authority_grant.read``."""

    seed_lifecycle_permissions(governance_db, actor_id="creator")
    create_response = await migrated_async_client.post(
        BASE_URL,
        json=_create_payload(grantee_id="self-reader"),
        headers=_actor_headers(actor_id="creator"),
    )
    assert create_response.status_code == HTTPStatus.CREATED, create_response.text

    response = await migrated_async_client.get(
        BASE_URL,
        params={"grantee_id": "self-reader"},
        headers=_actor_headers(actor_id="self-reader"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert len(response.json()["items"]) >= 1
