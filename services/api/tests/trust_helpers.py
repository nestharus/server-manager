from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.members import MemberRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


MEMBERS_URL = "/api/v1/members"
TRUST_SIGNALS_URL = "/api/v1/trust/signals"
TRUST_RECOMPUTE_URL = "/api/v1/trust/recompute/{member_id}"
TRUST_COMPUTE_URL = "/api/v1/trust/compute/{member_id}"


def actor_headers(
    *,
    actor_id: str = "operator",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def make_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def grant_permissions(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
    scope_kind: str = "global",
    scope_id: str | None = None,
) -> None:
    with use_audit_context(make_audit_context()):
        grant_authority(
            db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "root"),
        )


def member_payload(
    *,
    discord_user_id: str | None = None,
    joined_at: datetime | None = None,
    originating_actor_id: str,
) -> dict[str, Any]:
    return {
        "discord_user_id": discord_user_id or str(uuid4()),
        "joined_at": (joined_at or datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)).isoformat(),
        "originating_actor_kind": "user",
        "originating_actor_id": originating_actor_id,
    }


async def create_member(client: Any, *, actor_id: str) -> MemberRead:
    response = await client.post(
        MEMBERS_URL,
        json=member_payload(originating_actor_id=actor_id),
        headers=actor_headers(actor_id=actor_id),
    )
    assert response.status_code == 201, response.text
    return MemberRead.model_validate(response.json())


def valid_trust_policy_content(
    *,
    default_score: int = 50,
    signal_weights: dict[str, int | float] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "score_floor": 0,
        "score_ceiling": 100,
        "default_score": default_score,
        "signal_weights": signal_weights or {"positive": 20, "negative": -20},
        "decay_rules": {},
        "level_thresholds": [
            {"tier": "low", "max_score": 39},
            {"tier": "medium", "max_score": 79},
            {"tier": "high", "max_score": 100},
        ],
    }


def seed_trust_policy_version(
    database_url: str,
    *,
    version_number: int,
    content: dict[str, Any] | None = None,
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
            (
                row_id,
                version_number,
                json.dumps(content or valid_trust_policy_content()),
                datetime.now(UTC),
            ),
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


def fetch_one(database_url: str, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(query, params).fetchone()
    assert row is not None
    return row


