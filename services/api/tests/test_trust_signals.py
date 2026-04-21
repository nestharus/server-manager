from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import psycopg
import pytest
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase

from tests.trust_helpers import (
    TRUST_COMPUTE_URL,
    TRUST_SIGNALS_URL,
    actor_headers,
    create_member,
    fetch_one,
    grant_permissions,
    seed_trust_policy_version,
    valid_trust_policy_content,
)


def _signal_payload(
    member_id: str,
    *,
    scope_kind: str = "global",
    scope_id: str | None = None,
    signal_type: str = "positive",
    observed_at: datetime | None = None,
    expires_at: datetime | None = None,
    value: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "member_id": member_id,
        "signal_type": signal_type,
        "scope": {"scope_kind": scope_kind},
        "value": value or {"schema_version": 1, "magnitude": 1},
        "observed_at": (observed_at or datetime(2025, 2, 1, tzinfo=UTC)).isoformat(),
    }
    if scope_id is not None:
        payload["scope"]["scope_id"] = scope_id  # type: ignore[index]
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    return payload


@pytest.mark.asyncio
async def test_create_signal_persists_fields_without_mutating_profile(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust signal create; D8 records signal state without changing profile."""
    actor_id = "signal-operator"
    seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=valid_trust_policy_content(
            signal_weights={
                "discord_account_age_days": 0,
                "has_avatar": 10,
                "has_verified_badge": 0,
            }
        ),
    )
    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write", "trust.signal.create"}),
    )
    member = await create_member(migrated_async_client, actor_id=actor_id)

    compute = await migrated_async_client.post(
        TRUST_COMPUTE_URL.format(member_id=member.id),
        json={
            "discord_account_age_days": 10,
            "has_avatar": True,
            "has_verified_badge": False,
            "account_flags": [],
            "originating_actor_kind": "user",
            "originating_actor_id": actor_id,
        },
        headers=actor_headers(actor_id=actor_id),
    )
    assert compute.status_code == HTTPStatus.CREATED, compute.text
    before = fetch_one(
        governance_dsn,
        """
        SELECT score, tier, h.current_seq AS version
        FROM trust_profiles AS tp
        JOIN aggregate_heads AS h
          ON h.aggregate_type = 'trust_profile'
         AND h.aggregate_id = tp.member_id::text
        WHERE tp.member_id = %s
        """,
        (member.id,),
    )

    observed_at = datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC)
    response = await migrated_async_client.post(
        TRUST_SIGNALS_URL,
        json=_signal_payload(str(member.id), observed_at=observed_at),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.headers["etag"] == '"1"'
    body = response.json()
    assert body["member_id"] == str(member.id)
    assert body["signal_type"] == "positive"
    assert body["scope"] == {"scope_kind": "global", "scope_id": None}
    assert body["value"] == {"schema_version": 1, "magnitude": 1}
    assert body["source_actor_kind"] == "user"
    assert body["source_actor_id"] == actor_id

    signal = fetch_one(
        governance_dsn,
        """
        SELECT member_id, signal_type, scope_kind, scope_id, scope, value,
               source_actor_kind, source_actor_id, observed_at
        FROM trust_signals
        WHERE id = %s
        """,
        (body["id"],),
    )
    assert signal["member_id"] == member.id
    assert signal["signal_type"] == "positive"
    assert signal["scope_kind"] == "global"
    assert signal["scope_id"] is None
    assert signal["scope"] == {"scope_kind": "global"}
    assert signal["value"] == {"schema_version": 1, "magnitude": 1}
    assert signal["source_actor_id"] == actor_id

    after = fetch_one(
        governance_dsn,
        """
        SELECT score, tier, h.current_seq AS version
        FROM trust_profiles AS tp
        JOIN aggregate_heads AS h
          ON h.aggregate_type = 'trust_profile'
         AND h.aggregate_id = tp.member_id::text
        WHERE tp.member_id = %s
        """,
        (member.id,),
    )
    assert after == before

    audit = fetch_one(
        governance_dsn,
        """
        SELECT aa.action_type,
               aa.request_json,
               ascg.change_type,
               ascg.payload_json,
               ascg.diff_json,
               h.current_seq
        FROM activity_actions AS aa
        JOIN activity_state_changes AS ascg ON ascg.action_id = aa.id
        JOIN aggregate_heads AS h
          ON h.aggregate_type = aa.aggregate_type
         AND h.aggregate_id = aa.aggregate_id
        WHERE aa.aggregate_type = 'trust_signal'
          AND aa.aggregate_id = %s
        """,
        (body["id"],),
    )
    assert audit["action_type"] == "trust.signal.created"
    assert audit["request_json"]["member_id"] == str(member.id)
    assert audit["request_json"]["observed_at"] == observed_at.isoformat().replace("+00:00", "Z")
    assert audit["change_type"] == "trust.signal.created"
    assert audit["payload_json"]["id"] == body["id"]
    assert audit["payload_json"]["member_id"] == str(member.id)
    assert audit["diff_json"]["signal_type"] == "positive"
    assert audit["current_seq"] == 1


@pytest.mark.asyncio
async def test_create_signal_requires_authority_at_scope(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC trust signal create; D7 requires authority at the requested scope."""
    actor_id = "chapter-denied"
    grant_permissions(governance_db, actor_id=actor_id, permissions=frozenset({"member.write"}))
    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"trust.signal.create"}),
        scope_kind="global",
        scope_id=None,
    )
    member = await create_member(migrated_async_client, actor_id=actor_id)

    response = await migrated_async_client.post(
        TRUST_SIGNALS_URL,
        json=_signal_payload(str(member.id), scope_kind="chapter", scope_id="chapter-a"),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "authority_decision_denied"


@pytest.mark.asyncio
async def test_create_signal_rejects_invalid_scope_shape(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC trust signal create; D2 rejects malformed scope and timestamp payloads."""
    actor_id = "invalid-signal"
    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.signal.create"}),
    )
    member = await create_member(migrated_async_client, actor_id=actor_id)

    naive_timestamp = _signal_payload(str(member.id))
    naive_timestamp["observed_at"] = "2025-02-01T00:00:00"
    invalid_payloads = [
        _signal_payload(str(member.id), scope_kind="global", scope_id="not-allowed"),
        _signal_payload(str(member.id), scope_kind="chapter"),
        _signal_payload(str(member.id), value={"magnitude": 1}),
        naive_timestamp,
    ]

    for payload in invalid_payloads:
        response = await migrated_async_client.post(
            TRUST_SIGNALS_URL,
            json=payload,
            headers=actor_headers(actor_id=actor_id),
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_create_signal_with_expires_at_persists_correctly(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust signal create; D2 persists aware expiry timestamps only."""
    actor_id = "expiry-signal"
    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.signal.create"}),
    )
    member = await create_member(migrated_async_client, actor_id=actor_id)
    observed_at = datetime(2025, 2, 1, tzinfo=UTC)
    expires_at = observed_at + timedelta(days=30)

    response = await migrated_async_client.post(
        TRUST_SIGNALS_URL,
        json=_signal_payload(str(member.id), observed_at=observed_at, expires_at=expires_at),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    row = fetch_one(
        governance_dsn,
        "SELECT expires_at FROM trust_signals WHERE id = %s",
        (response.json()["id"],),
    )
    assert row["expires_at"] == expires_at

    invalid = await migrated_async_client.post(
        TRUST_SIGNALS_URL,
        json=_signal_payload(str(member.id), observed_at=observed_at, expires_at=observed_at),
        headers=actor_headers(actor_id=actor_id),
    )
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, invalid.text


@pytest.mark.asyncio
async def test_trust_signal_db_constraints_reject_malformed_json(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust signal create; D2 keeps database constraints as the final boundary."""
    actor_id = "db-constraint"
    grant_permissions(governance_db, actor_id=actor_id, permissions=frozenset({"member.write"}))
    member = await create_member(migrated_async_client, actor_id=actor_id)

    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO trust_signals (
                    id, member_id, signal_type, scope_kind, scope_id, scope,
                    value, source_actor_kind, source_actor_id, observed_at
                )
                VALUES (%s, %s, 'positive', 'global', NULL, %s::jsonb,
                        %s::jsonb, 'user', 'operator', %s)
                """,
                (
                    uuid4(),
                    member.id,
                    '{"scope_kind":"member"}',
                    '{"magnitude":1}',
                    datetime(2025, 2, 1, tzinfo=UTC),
                ),
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO trust_signals (
                    id, member_id, signal_type, scope_kind, scope_id, scope,
                    value, source_actor_kind, source_actor_id, observed_at
                )
                VALUES (%s, %s, 'positive', 'chapter', '', %s::jsonb,
                        %s::jsonb, 'user', 'operator', %s)
                """,
                (
                    uuid4(),
                    member.id,
                    '{"scope_kind":"chapter","scope_id":""}',
                    '{"schema_version":1}',
                    datetime(2025, 2, 1, tzinfo=UTC),
                ),
            )
