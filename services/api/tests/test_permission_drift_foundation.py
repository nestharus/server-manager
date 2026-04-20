"""Contract tests for WU-006B: permission drift foundation (AC1).

Pins the paired-null intent anchoring rule, the status value-membership
CHECK, the ``ON DELETE RESTRICT`` FK from drift to intent, and the
service-level status transition path.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.permissions import (
    PermissionDriftRead,
    PermissionIntentCreate,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.permissions import (
    create_permission_intent,
    update_permission_drift_status,
)


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _drift_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": uuid4(),
        "permission_intent_id": uuid4(),
        "intent_version": 1,
        "actual_bits": "16",
        "actual_allow_bits": None,
        "actual_deny_bits": None,
        "intended_bits": "24",
        "intended_allow_bits": None,
        "intended_deny_bits": None,
        "status": "detected",
        "detected_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def _seed_guild_intent(
    governance_db: PostgresDatabase,
    *,
    scope_id: str = "ch-1",
) -> UUID:
    request = PermissionIntentCreate.model_validate(
        {
            "kind": "guild_role",
            "scope_kind": "chapter",
            "scope_id": scope_id,
            "role_id": "R1",
            "permission_bits": "123",
            "reason": None,
            "temporary": False,
            "expires_at": None,
        }
    )
    with use_audit_context(_make_audit_context()):
        create_permission_intent(governance_db, request)

    # The intent id is not returned from the service in this foundation
    # slice; fetch the single row we just created.
    with governance_db.connection() as conn, conn.cursor(
        row_factory=dict_row
    ) as cur:
        rows = cur.execute(
            "SELECT id FROM permission_intents WHERE scope_id = %s",
            (scope_id,),
        ).fetchall()
    assert len(rows) == 1
    return rows[0]["id"]


def _seed_drift_row(
    database_url: str,
    *,
    permission_intent_id: UUID | None,
    intent_version: int | None,
    status: str = "detected",
) -> UUID:
    drift_id = uuid4()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO permission_drift (
                id, permission_intent_id, intent_version,
                actual_bits, actual_allow_bits, actual_deny_bits,
                intended_bits, intended_allow_bits, intended_deny_bits,
                status, detected_at
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            """,
            (
                drift_id,
                permission_intent_id,
                intent_version,
                16,
                None,
                None,
                24,
                None,
                None,
                status,
                datetime.now(UTC),
            ),
        )
    return drift_id


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# JSON round-trip (AC1)
# ---------------------------------------------------------------------------


def test_drift_round_trips_to_json() -> None:
    """A populated drift envelope must round-trip through the canonical
    ``model_dump(mode='json')`` form without field loss."""

    original = PermissionDriftRead(**_drift_kwargs())
    restored = PermissionDriftRead.model_validate(
        original.model_dump(mode="json")
    )

    assert restored.id == original.id
    assert restored.permission_intent_id == original.permission_intent_id
    assert restored.intent_version == original.intent_version
    assert restored.actual_bits == original.actual_bits
    assert restored.intended_bits == original.intended_bits
    assert restored.status == original.status
    assert restored.detected_at == original.detected_at


def test_orphan_drift_round_trips() -> None:
    """An orphan drift row — no known intent — must be a valid contract
    shape with both ``permission_intent_id`` and ``intent_version`` null."""

    drift = PermissionDriftRead(
        **_drift_kwargs(permission_intent_id=None, intent_version=None)
    )
    assert drift.permission_intent_id is None
    assert drift.intent_version is None


# ---------------------------------------------------------------------------
# Paired-null intent anchoring invariant (D4)
# ---------------------------------------------------------------------------


def test_drift_rejects_intent_id_without_version() -> None:
    """If ``permission_intent_id`` is set, ``intent_version`` must be set
    too. Linked drift rows always carry the version they were detected at."""

    with pytest.raises(ValidationError):
        PermissionDriftRead(
            **_drift_kwargs(permission_intent_id=uuid4(), intent_version=None)
        )


def test_drift_rejects_version_without_intent_id() -> None:
    """A version number without a linked intent id is nonsensical; the
    contract must refuse it up front."""

    with pytest.raises(ValidationError):
        PermissionDriftRead(
            **_drift_kwargs(permission_intent_id=None, intent_version=1)
        )


# ---------------------------------------------------------------------------
# Status transitions (D8 mirror for drift)
# ---------------------------------------------------------------------------


def test_drift_status_transitions_detected_to_acknowledged(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """The service-layer transition ``detected -> acknowledged`` must succeed
    and route through ``validated_update`` so contract invariants are
    re-checked on the patch."""

    intent_id = _seed_guild_intent(governance_db)
    drift_id = _seed_drift_row(
        governance_dsn,
        permission_intent_id=intent_id,
        intent_version=1,
        status="detected",
    )

    with use_audit_context(_make_audit_context()):
        update_permission_drift_status(
            governance_db, drift_id=drift_id, status="acknowledged"
        )

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT status FROM permission_drift WHERE id = %s",
            (drift_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# DB-level invariants
# ---------------------------------------------------------------------------


def test_drift_status_rejects_invalid_value(governance_dsn: str) -> None:
    """The DB ``CHECK`` must block arbitrary status strings at INSERT time,
    not just at the service layer."""

    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO permission_drift (
                    id, permission_intent_id, intent_version,
                    actual_bits, actual_allow_bits, actual_deny_bits,
                    intended_bits, intended_allow_bits, intended_deny_bits,
                    status, detected_at
                )
                VALUES (
                    %s, NULL, NULL,
                    NULL, NULL, NULL,
                    NULL, NULL, NULL,
                    'invalid', %s
                )
                """,
                (uuid4(), datetime.now(UTC)),
            )


def test_drift_fk_restrict_on_intent_delete(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``permission_drift.permission_intent_id`` must be
    ``ON DELETE RESTRICT`` — drift is audit history and must never be
    silently cascaded away when an intent is deleted."""

    intent_id = _seed_guild_intent(governance_db)
    _seed_drift_row(
        governance_dsn,
        permission_intent_id=intent_id,
        intent_version=1,
    )

    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "DELETE FROM permission_intents WHERE id = %s",
                (intent_id,),
            )
