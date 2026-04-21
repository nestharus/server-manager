from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.trust import InvalidTrustPolicyError, TrustProfileRead
from app.repositories.db import PostgresDatabase
from app.services.trust import compute_score

from tests.trust_helpers import (
    TRUST_RECOMPUTE_URL,
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
    signal_type: str = "positive",
    observed_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "member_id": member_id,
        "signal_type": signal_type,
        "scope": {"scope_kind": "global"},
        "value": {"schema_version": 1, "magnitude": 1},
        "observed_at": (observed_at or datetime(2025, 2, 1, tzinfo=UTC)).isoformat(),
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    return payload


async def _create_signal(client: AsyncClient, *, actor_id: str, member_id: str, **kwargs: Any) -> str:
    response = await client.post(
        TRUST_SIGNALS_URL,
        json=_signal_payload(member_id, **kwargs),
        headers=actor_headers(actor_id=actor_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()["id"]


async def _setup_recompute_member(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    actor_id: str,
) -> str:
    grant_permissions(
        db,
        actor_id=actor_id,
        permissions=frozenset({"member.write", "trust.signal.create"}),
    )
    member = await create_member(client, actor_id=actor_id)
    grant_permissions(
        db,
        actor_id=actor_id,
        permissions=frozenset({"trust.recompute"}),
        scope_kind="member",
        scope_id=str(member.id),
    )
    return str(member.id)


@pytest.mark.asyncio
async def test_recompute_pins_current_policy_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D5 pins the current policy version in the profile."""
    actor_id = "recompute-policy"
    seed_trust_policy_version(governance_dsn, version_number=1)
    latest_policy_id = seed_trust_policy_version(governance_dsn, version_number=2)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)
    await _create_signal(migrated_async_client, actor_id=actor_id, member_id=member_id)

    response = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    profile = TrustProfileRead.model_validate(response.json())
    assert profile.policy_version_id == latest_policy_id
    assert profile.config_version == 2
    assert response.headers["etag"] == '"1"'


@pytest.mark.asyncio
async def test_recompute_deterministic_for_same_inputs(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D10 produces deterministic output for identical inputs."""
    actor_id = "recompute-deterministic"
    seed_trust_policy_version(governance_dsn, version_number=1)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)
    first_signal_id = await _create_signal(
        migrated_async_client,
        actor_id=actor_id,
        member_id=member_id,
        observed_at=datetime(2025, 2, 1, tzinfo=UTC),
    )
    second_signal_id = await _create_signal(
        migrated_async_client,
        actor_id=actor_id,
        member_id=member_id,
        observed_at=datetime(2025, 2, 2, tzinfo=UTC),
    )

    first = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )
    second = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )

    assert first.status_code == HTTPStatus.OK, first.text
    assert second.status_code == HTTPStatus.OK, second.text
    first_profile = TrustProfileRead.model_validate(first.json())
    second_profile = TrustProfileRead.model_validate(second.json())
    assert first_profile.score == second_profile.score == 90
    assert first_profile.tier == second_profile.tier == "high"
    assert first_profile.signals == second_profile.signals
    assert first_profile.signals["signal_ids"] == [first_signal_id, second_signal_id]
    assert first_profile.policy_version_id == second_profile.policy_version_id
    assert first_profile.config_version == second_profile.config_version == 1


@pytest.mark.asyncio
async def test_recompute_produces_new_profile_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D8 advances optimistic-lock profile versions."""
    actor_id = "recompute-version"
    seed_trust_policy_version(governance_dsn, version_number=1)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)

    first = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )
    second = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )

    assert first.status_code == HTTPStatus.OK, first.text
    assert second.status_code == HTTPStatus.OK, second.text
    assert first.headers["etag"] == '"1"'
    assert second.headers["etag"] == '"2"'
    assert TrustProfileRead.model_validate(second.json()).version == 2


@pytest.mark.asyncio
async def test_recompute_returns_409_on_stale_conflict_after_retry(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC trust recompute; D8 returns conflict after retrying stale mutations."""
    actor_id = "recompute-conflict"
    seed_trust_policy_version(governance_dsn, version_number=1)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)

    def stale_mutation(**_kwargs: object) -> object:
        from app.contracts.mutations import StaleMutationError

        raise StaleMutationError(
            aggregate_type="trust_profile",
            aggregate_id=member_id,
            expected_version=0,
            current_version=1,
        )

    monkeypatch.setattr("app.services.trust.mutate_entity", stale_mutation)
    response = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "trust_recompute_conflict"


@pytest.mark.asyncio
async def test_recompute_honors_expired_signals_by_ignoring_them(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D10 excludes expired signals from deterministic scoring."""
    actor_id = "recompute-expiry"
    seed_trust_policy_version(governance_dsn, version_number=1)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)
    now = datetime.now(UTC)
    await _create_signal(
        migrated_async_client,
        actor_id=actor_id,
        member_id=member_id,
        observed_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )
    active_signal_id = await _create_signal(
        migrated_async_client,
        actor_id=actor_id,
        member_id=member_id,
        observed_at=now - timedelta(days=2),
        expires_at=now + timedelta(days=1),
    )

    response = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    profile = TrustProfileRead.model_validate(response.json())
    assert profile.score == 70
    assert profile.signals["signal_ids"] == [active_signal_id]


@pytest.mark.asyncio
async def test_recompute_requires_trust_recompute_at_member_scope(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D7 authorizes recompute at member scope only."""
    actor_id = "recompute-authority"
    seed_trust_policy_version(governance_dsn, version_number=1)
    grant_permissions(governance_db, actor_id=actor_id, permissions=frozenset({"member.write"}))
    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"trust.recompute"}),
        scope_kind="global",
        scope_id=None,
    )
    member = await create_member(migrated_async_client, actor_id=actor_id)

    denied = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member.id),
        headers=actor_headers(actor_id=actor_id),
    )
    assert denied.status_code == HTTPStatus.FORBIDDEN, denied.text

    grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"trust.recompute"}),
        scope_kind="member",
        scope_id=str(member.id),
    )
    allowed = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member.id),
        headers=actor_headers(actor_id=actor_id),
    )
    assert allowed.status_code == HTTPStatus.OK, allowed.text


@pytest.mark.asyncio
async def test_recompute_audit_records_correct_diff(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC trust recompute; D8 records scoped audit diff through mutate_entity."""
    actor_id = "recompute-audit"
    policy_id = seed_trust_policy_version(governance_dsn, version_number=1)
    member_id = await _setup_recompute_member(migrated_async_client, governance_db, actor_id=actor_id)
    signal_id = await _create_signal(migrated_async_client, actor_id=actor_id, member_id=member_id)

    response = await migrated_async_client.post(
        TRUST_RECOMPUTE_URL.format(member_id=member_id),
        headers=actor_headers(actor_id=actor_id),
    )
    assert response.status_code == HTTPStatus.OK, response.text

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT aa.action_type,
                   aa.scope_kind,
                   aa.scope_id,
                   aa.request_json,
                   ascg.change_type,
                   ascg.diff_json
            FROM activity_actions AS aa
            JOIN activity_state_changes AS ascg ON ascg.action_id = aa.id
            WHERE aa.aggregate_type = 'trust_profile'
              AND aa.aggregate_id = %s
            ORDER BY aa.id DESC
            LIMIT 1
            """,
            (member_id,),
        ).fetchone()
    assert row is not None
    assert row["action_type"] == "trust.recompute"
    assert row["scope_kind"] == "member"
    assert row["scope_id"] == member_id
    assert row["request_json"] == {"member_id": member_id}
    assert row["change_type"] == "trust.recomputed"
    assert row["diff_json"]["score"] == {"old": None, "new": 70}
    assert row["diff_json"]["tier"] == {"old": None, "new": "medium"}
    assert row["diff_json"]["policy_version_id"] == {"old": None, "new": str(policy_id)}
    assert row["diff_json"]["config_version"] == {"old": None, "new": 1}
    assert row["diff_json"]["signal_ids"] == {"old": [], "new": [signal_id]}


def test_policy_with_decay_rules_rejected_until_supported() -> None:
    """AC trust recompute; D10 rejects unsupported decay policies explicitly."""
    content = valid_trust_policy_content()
    content["decay_rules"] = {"half_life_days": 30}

    with pytest.raises(InvalidTrustPolicyError, match="decay_rules not yet supported"):
        compute_score([], content)


def test_tier_selection_independent_of_policy_order() -> None:
    """AC trust recompute; D10 sorts policy thresholds before tier selection."""
    content = valid_trust_policy_content(default_score=50)
    content["level_thresholds"] = [
        {"tier": "high", "max_score": 100},
        {"tier": "low", "max_score": 39},
        {"tier": "medium", "max_score": 79},
    ]

    score, tier, summary = compute_score([], content)

    assert score == 50
    assert tier == "medium"
    assert summary["count"] == 0


def test_no_trust_signal_bypass_remains(repo_root: Path) -> None:
    """AC trust recompute; D8 keeps profile and signal writes behind mutate_entity."""
    allowed = {
        Path("services/api/app/services/trust.py"),
        Path("services/api/app/repositories/trust.py"),
    }
    patterns = (
        "INSERT INTO trust_signals",
        "UPDATE trust_signals",
        "DELETE FROM trust_signals",
        "UPDATE trust_profiles",
        "INSERT INTO trust_profiles",
        "DELETE FROM trust_profiles",
    )
    violations: list[str] = []
    for path in repo_root.rglob("*.py"):
        rel = path.relative_to(repo_root)
        if rel in allowed:
            continue
        if rel.parts[0] in {"migrations", "risk", "research", "proposals"}:
            continue
        if rel.parts[:2] == ("services", "api") and len(rel.parts) > 2 and rel.parts[2] == "tests":
            continue
        text = path.read_text()
        for pattern in patterns:
            if pattern in text:
                violations.append(f"{rel}: {pattern}")

    assert violations == []
