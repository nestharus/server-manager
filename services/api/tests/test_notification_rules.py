from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


BASE_URL = "/api/v1/notification-rules"


def _actor_headers(
    *,
    actor_id: str = "operator",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _make_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _rule_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "trigger": {
            "event_type": "chapter.transition",
            "payload_filters": {"to_state": "active"},
        },
        "scope_kind": "chapter",
        "scope_id": "chapter-1",
        "recipients": {"kind": "discord_users", "user_ids": ["1001", "1002"]},
        "channel": "designated_channel",
        "template": {
            "title": "Chapter ${payload_chapter_id}",
            "body": "Moved to ${payload_to_state}",
        },
        "actionable": True,
        "grouping": "per_root_cause",
        "enabled": True,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _seed_permissions(
    db: PostgresDatabase,
    *,
    grantee_id: str = "operator",
    permissions: frozenset[str],
) -> None:
    with use_audit_context(_make_audit_context()):
        grant_authority(
            db=db,
            grantee_id=grantee_id,
            scope_kind="global",
            scope_id=None,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


async def _create_rule(
    client: AsyncClient,
    *,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    response = await client.post(
        BASE_URL,
        json=_rule_payload() if payload is None else payload,
        headers=_actor_headers() if headers is None else headers,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json(), response.headers["etag"]


def _fetch_rule_row(dsn: str, rule_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, trigger_json, scope_kind, scope_id, recipients_json,
                   channel, template_json, actionable, grouping, enabled
            FROM notification_rules
            WHERE id = %s
            """,
            (str(rule_id),),
        ).fetchone()


def _fetch_head_row(dsn: str, rule_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT aggregate_type, aggregate_id, current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'notification_rule'
              AND aggregate_id = %s
            """,
            (str(rule_id),),
        ).fetchone()


def _fetch_create_action(dsn: str, rule_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT action_type, aggregate_type, aggregate_id, request_json
            FROM activity_actions
            WHERE aggregate_type = 'notification_rule'
              AND aggregate_id = %s
              AND action_type = 'notification_rule.create'
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(rule_id),),
        ).fetchone()


def _fetch_patch_action(dsn: str, rule_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT action_type, aggregate_type, aggregate_id, request_json
            FROM activity_actions
            WHERE aggregate_type = 'notification_rule'
              AND aggregate_id = %s
              AND action_type = 'notification_rule.patch'
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(rule_id),),
        ).fetchone()


def _fetch_latest_state_change(dsn: str, rule_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT aggregate_seq, change_type, payload_json
            FROM activity_state_changes
            WHERE aggregate_type = 'notification_rule'
              AND aggregate_id = %s
              AND change_type = 'notification_rule.updated'
            ORDER BY aggregate_seq DESC
            LIMIT 1
            """,
            (str(rule_id),),
        ).fetchone()


@pytest.mark.asyncio
async def test_create_rule_persists_all_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )
    payload = _rule_payload(
        recipients={"kind": "discord_users", "user_ids": ["2001", "2002"]},
        channel="dm",
        grouping="per_event",
        actionable=False,
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert response.headers["etag"] == '"1"'
    assert body["trigger"] == payload["trigger"]
    assert body["scope_kind"] == "chapter"
    assert body["scope_id"] == "chapter-1"
    assert body["recipients"] == payload["recipients"]
    assert body["channel"] == "dm"
    assert body["template"] == payload["template"]
    assert body["actionable"] is False
    assert body["grouping"] == "per_event"
    assert body["enabled"] is True
    assert body["version"] == 1

    row = _fetch_rule_row(governance_dsn, body["id"])
    assert row is not None
    assert row["trigger_json"] == payload["trigger"]
    assert row["scope_kind"] == "chapter"
    assert row["scope_id"] == "chapter-1"
    assert row["recipients_json"] == payload["recipients"]
    assert row["channel"] == "dm"
    assert row["template_json"] == payload["template"]
    assert row["actionable"] is False
    assert row["grouping"] == "per_event"
    assert row["enabled"] is True

    head = _fetch_head_row(governance_dsn, body["id"])
    assert head is not None
    assert head["aggregate_type"] == "notification_rule"
    assert head["aggregate_id"] == body["id"]
    assert int(head["current_seq"]) == 1


@pytest.mark.asyncio
async def test_patch_rule_with_current_version_succeeds(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )
    created, etag = await _create_rule(migrated_async_client)
    patch = {
        "grouping": "per_event",
        "enabled": False,
        "channel": "dm",
        "template": {
            "title": "Replay ${event_type}",
            "body": "Chapter ${payload_chapter_id}",
        },
    }

    response = await migrated_async_client.patch(
        f"{BASE_URL}/{created['id']}",
        json=patch,
        headers={**_actor_headers(), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert response.headers["etag"] == '"2"'
    assert body["id"] == created["id"]
    assert body["grouping"] == "per_event"
    assert body["enabled"] is False
    assert body["channel"] == "dm"
    assert body["template"] == patch["template"]
    assert body["version"] == 2

    row = _fetch_rule_row(governance_dsn, created["id"])
    assert row is not None
    assert row["grouping"] == "per_event"
    assert row["enabled"] is False
    assert row["channel"] == "dm"
    assert row["template_json"] == patch["template"]

    head = _fetch_head_row(governance_dsn, created["id"])
    assert head is not None
    assert int(head["current_seq"]) == 2

    action = _fetch_patch_action(governance_dsn, created["id"])
    assert action is not None
    assert action["action_type"] == "notification_rule.patch"

    state_change = _fetch_latest_state_change(governance_dsn, created["id"])
    assert state_change is not None
    assert state_change["aggregate_seq"] == 2
    assert state_change["payload_json"]["version"] == 2
    assert state_change["payload_json"]["updated_at"] == body["updated_at"]
    assert state_change["payload_json"]["updated_at"] != created["updated_at"]


@pytest.mark.asyncio
async def test_patch_rule_stale_version_returns_412(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )
    created, stale_etag = await _create_rule(migrated_async_client)
    first = await migrated_async_client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"enabled": False},
        headers={**_actor_headers(), "If-Match": stale_etag},
    )
    assert first.status_code == HTTPStatus.OK, first.text

    response = await migrated_async_client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"grouping": "per_event"},
        headers={**_actor_headers(), "If-Match": stale_etag},
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED, response.text
    body = response.json()
    assert body["code"] == "stale_notification_rule_version"
    assert body["expected_version"] == 1
    assert body["current_version"] == 2


@pytest.mark.asyncio
async def test_list_rules_filters_by_scope(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )
    chapter_one, _ = await _create_rule(
        migrated_async_client,
        payload=_rule_payload(scope_id="chapter-1"),
    )
    chapter_two, _ = await _create_rule(
        migrated_async_client,
        payload=_rule_payload(scope_id="chapter-2"),
    )
    global_rule, _ = await _create_rule(
        migrated_async_client,
        payload=_rule_payload(
            scope_kind="global",
            scope_id=None,
            grouping="per_event",
            channel="dm",
        ),
    )

    response = await migrated_async_client.get(
        BASE_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert ids == {chapter_one["id"]}
    assert chapter_two["id"] not in ids
    assert global_rule["id"] not in ids


@pytest.mark.asyncio
async def test_rule_create_requires_notification_write_permission(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,  # noqa: ARG001
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read"}),
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=_rule_payload(),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    body = response.json()
    assert body["code"] == "authority_decision_denied"
    assert body["decision"]["denial_reason"] == "permission_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope_kind", "scope_id"),
    [
        ("global", "chapter-1"),
        ("chapter", None),
        ("member", None),
    ],
)
async def test_rule_create_rejects_scope_kind_scope_id_mismatch(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,  # noqa: ARG001
    scope_kind: str,
    scope_id: str | None,
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=_rule_payload(scope_kind=scope_kind, scope_id=scope_id),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_rule_create_audit_payload_includes_all_rule_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_permissions(
        governance_db,
        permissions=frozenset({"notification.read", "notification.write"}),
    )
    payload = _rule_payload(
        actionable=False,
        grouping="per_event",
        enabled=False,
    )
    created, _etag = await _create_rule(
        migrated_async_client,
        payload=payload,
    )

    action = _fetch_create_action(governance_dsn, created["id"])

    assert action is not None
    assert action["action_type"] == "notification_rule.create"
    assert action["aggregate_type"] == "notification_rule"
    assert action["aggregate_id"] == created["id"]
    assert set(action["request_json"]) == {
        "trigger_json",
        "scope_kind",
        "scope_id",
        "recipients_json",
        "channel",
        "template_json",
        "actionable",
        "grouping",
        "enabled",
    }
    assert action["request_json"] == {
        "trigger_json": payload["trigger"],
        "scope_kind": payload["scope_kind"],
        "scope_id": payload["scope_id"],
        "recipients_json": payload["recipients"],
        "channel": payload["channel"],
        "template_json": payload["template"],
        "actionable": payload["actionable"],
        "grouping": payload["grouping"],
        "enabled": payload["enabled"],
    }


def test_notification_dispatcher_grants_seeded_without_notification_write(
    fresh_migrated_postgres_db: str,
) -> None:
    with psycopg.connect(fresh_migrated_postgres_db, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT permissions
            FROM authority_grants
            WHERE grantee_id = 'notification-dispatcher'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND revoked_at IS NULL
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()

    assert row is not None
    assert set(row["permissions"]) == {
        "notification.read",
        "notification.deliver",
    }
    assert "notification.write" not in set(row["permissions"])
