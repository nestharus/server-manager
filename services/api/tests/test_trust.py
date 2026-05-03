from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.members import MemberRead
from app.contracts.trust import TrustProfileRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


MEMBERS_URL = "/api/v1/members"
TRUST_URL = "/api/v1/trust"
COMPUTE_URL = "/api/v1/trust/compute/{member_id}"


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


def _grant_permissions(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
) -> None:
    with use_audit_context(_make_audit_context()):
        grant_authority(
            db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "root"),
        )


def _member_payload(
    *,
    discord_user_id: str,
    joined_at: datetime,
    originating_actor_id: str,
) -> dict[str, Any]:
    return {
        "discord_user_id": discord_user_id,
        "joined_at": joined_at.isoformat(),
        "originating_actor_kind": "user",
        "originating_actor_id": originating_actor_id,
    }


def _trust_signals(
    *,
    discord_account_age_days: int = 14,
    has_avatar: bool = True,
    has_verified_badge: bool = False,
    account_flags: list[str] | None = None,
    originating_actor_id: str,
) -> dict[str, Any]:
    return {
        "discord_account_age_days": discord_account_age_days,
        "has_avatar": has_avatar,
        "has_verified_badge": has_verified_badge,
        "account_flags": account_flags or [],
        "originating_actor_kind": "user",
        "originating_actor_id": originating_actor_id,
    }


def _seed_trust_policy_version(
    database_url: str,
    *,
    version_number: int,
    content: dict[str, Any],
) -> UUID:
    row_id = uuid4()
    aggregate_id = "trust_computation|global|"

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO policy_versions (
                id, policy_type, scope_kind, scope_id,
                version_number, content, effective_at
            )
            VALUES (%s, 'trust_computation', 'global', NULL, %s, %s::jsonb, %s)
            """,
            (row_id, version_number, json.dumps(content), datetime.now(UTC)),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type, aggregate_id, current_seq, latest_change_id
            )
            VALUES ('policy_version', %s, %s, NULL)
            ON CONFLICT (aggregate_type, aggregate_id)
            DO UPDATE SET current_seq = EXCLUDED.current_seq
            """,
            (aggregate_id, version_number),
        )

    return row_id


def _valid_trust_policy_rules() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "score_floor": 0,
        "score_ceiling": 100,
        "default_score": 50,
        "signal_weights": {
            "discord_account_age_days": 2,
            "has_avatar": 7,
            "has_verified_badge": 13,
        },
        "decay_rules": {},
        "level_thresholds": [
            {"tier": "low", "max_score": 39},
            {"tier": "medium", "max_score": 79},
            {"tier": "high", "max_score": 100},
        ],
    }


def _fetch_trust_profile_count(database_url: str, member_id: UUID | str) -> int:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM trust_profiles
            WHERE member_id = %s
            """,
            (str(member_id),),
        ).fetchone()
    assert row is not None
    return int(row["count"])


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_compute_trust_requires_trust_write_permission(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_compute_trust_creates_profile_with_current_policy_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=trust_compute_real_member_regression;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C4.
    """
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    current_policy_id = _seed_trust_policy_version(
        governance_dsn,
        version_number=2,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write", "trust.read"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    trust = TrustProfileRead.model_validate(response.json())
    assert trust.member_id == member.id
    assert trust.policy_version_id == current_policy_id
    assert trust.version == 1
    assert response.headers["etag"] == '"1"'
    assert _fetch_trust_profile_count(governance_dsn, member.id) == 1

    read_response = await migrated_async_client.get(
        f"{TRUST_URL}/{member.id}",
        headers=_actor_headers(actor_id=actor_id),
    )
    assert read_response.status_code == HTTPStatus.OK, read_response.text
    read_profile = TrustProfileRead.model_validate(read_response.json())
    assert read_profile == trust
    assert read_response.headers["etag"] == '"1"'


@pytest.mark.asyncio
async def test_compute_trust_rejects_synthetic_member_subject(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-4; named_risk=trust_compute_synthetic_subject;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C4.
    """
    actor_id = "synthetic-compute-operator"
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"trust.write"}),
    )
    synthetic = synthetic_member_guard_member_factory.synthetic()

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=synthetic.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "trust_subject_synthetic_not_allowed"
    assert _fetch_trust_profile_count(governance_dsn, synthetic.id) == 0


@pytest.mark.asyncio
async def test_compute_trust_is_deterministic_given_same_signals_and_policy(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    policy_id = _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    signals = _trust_signals(originating_actor_id=actor_id)

    first_member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    second_member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    first_member = MemberRead.model_validate(first_member_response.json())
    second_member = MemberRead.model_validate(second_member_response.json())

    first_response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=first_member.id),
        json=signals,
        headers=_actor_headers(actor_id=actor_id),
    )
    second_response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=second_member.id),
        json=signals,
        headers=_actor_headers(actor_id=actor_id),
    )

    assert first_response.status_code == HTTPStatus.CREATED, first_response.text
    assert second_response.status_code == HTTPStatus.CREATED, second_response.text
    first = TrustProfileRead.model_validate(first_response.json())
    second = TrustProfileRead.model_validate(second_response.json())
    assert first.policy_version_id == policy_id
    assert second.policy_version_id == policy_id
    assert first.score == second.score
    assert first.tier == second.tier
    assert first.signals == second.signals


@pytest.mark.asyncio
async def test_compute_trust_returns_existing_profile_on_retry(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())
    signals = _trust_signals(originating_actor_id=actor_id)

    first = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=signals,
        headers=_actor_headers(actor_id=actor_id),
    )
    second = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=signals,
        headers=_actor_headers(actor_id=actor_id),
    )

    assert first.status_code == HTTPStatus.CREATED, first.text
    assert second.status_code == HTTPStatus.OK, second.text
    first_profile = TrustProfileRead.model_validate(first.json())
    second_profile = TrustProfileRead.model_validate(second.json())
    assert second_profile == first_profile
    assert second.headers["etag"] == first.headers["etag"]
    assert _fetch_trust_profile_count(governance_dsn, member.id) == 1


@pytest.mark.asyncio
async def test_compute_trust_concurrent_same_member_returns_same_profile_to_both(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())
    signals = _trust_signals(originating_actor_id=actor_id)

    first, second = await asyncio.gather(
        migrated_async_client.post(
            COMPUTE_URL.format(member_id=member.id),
            json=signals,
            headers=_actor_headers(actor_id=actor_id),
        ),
        migrated_async_client.post(
            COMPUTE_URL.format(member_id=member.id),
            json=signals,
            headers=_actor_headers(actor_id=actor_id),
        ),
    )

    assert {first.status_code, second.status_code} == {
        HTTPStatus.CREATED,
        HTTPStatus.OK,
    }
    first_profile = TrustProfileRead.model_validate(first.json())
    second_profile = TrustProfileRead.model_validate(second.json())
    assert second_profile == first_profile
    assert _fetch_trust_profile_count(governance_dsn, member.id) == 1


@pytest.mark.asyncio
async def test_compute_trust_returns_409_when_no_trust_policy(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "no_trust_policy_configured"


@pytest.mark.asyncio
async def test_compute_trust_returns_409_when_policy_shape_invalid(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content={"unexpected": {"shape": True}},
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "invalid_trust_policy"


@pytest.mark.asyncio
async def test_compute_trust_returns_409_when_policy_weights_missing(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    content = _valid_trust_policy_rules()
    del content["signal_weights"]
    _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=content,
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "invalid_trust_policy"


@pytest.mark.asyncio
async def test_trust_profile_stores_policy_version_id_for_replay(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    policy_id = _seed_trust_policy_version(
        governance_dsn,
        version_number=1,
        content=_valid_trust_policy_rules(),
    )
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.write"}),
    )

    member_response = await migrated_async_client.post(
        MEMBERS_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    member = MemberRead.model_validate(member_response.json())

    response = await migrated_async_client.post(
        COMPUTE_URL.format(member_id=member.id),
        json=_trust_signals(originating_actor_id=actor_id),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT policy_version_id
            FROM trust_profiles
            WHERE member_id = %s
            """,
            (member.id,),
        ).fetchone()
    assert row is not None
    assert row["policy_version_id"] == policy_id


@pytest.mark.asyncio
async def test_member_onboarder_service_actor_grants_seeded(
    fresh_migrated_postgres_db: str,
) -> None:
    with psycopg.connect(fresh_migrated_postgres_db, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT grantee_id, scope_kind, scope_id, permissions
            FROM authority_grants
            WHERE grantee_id = 'member-onboarder'
            ORDER BY id ASC
            """
        ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row["grantee_id"] == "member-onboarder"
    assert row["scope_kind"] == "global"
    assert row["scope_id"] is None
    assert set(row["permissions"]) == {
        "member.read",
        "member.write",
        "trust.read",
        "trust.write",
    }
