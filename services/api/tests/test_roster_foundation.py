"""Contract tests for WU-007C: roster foundation (AC4).

Pins ``mutate_entity()``-based versioning, the FK to ``chapter_roles.id``,
the typed ``RosterRoleNotFoundError`` translation, and the full D8 status
transition matrix.
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
from app.contracts.chapter_roles import ChapterRoleCreate
from app.contracts.roster import (
    InvalidRosterStatusTransitionError,
    RosterEntryCreate,
    RosterEntryRead,
    RosterRoleNotFoundError,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.chapter_roles import create_chapter_role
from app.services.roster import (
    create_roster_entry,
    transition_roster_status,
)


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _seed_chapter_role(
    governance_db: PostgresDatabase,
    *,
    chapter_id: str = "ch-1",
    ordinal: int = 10,
) -> UUID:
    request = ChapterRoleCreate.model_validate(
        {
            "chapter_id": chapter_id,
            "template_id": None,
            "name": f"role-{ordinal}",
            "ordinal": ordinal,
            "triggers_succession": False,
        }
    )
    with use_audit_context(_make_audit_context()):
        create_chapter_role(governance_db, request)

    with governance_db.connection() as conn, conn.cursor(
        row_factory=dict_row
    ) as cur:
        rows = cur.execute(
            "SELECT id FROM chapter_roles WHERE chapter_id = %s AND ordinal = %s",
            (chapter_id, ordinal),
        ).fetchall()
    assert len(rows) == 1
    return rows[0]["id"]


def _roster_create_kwargs(role_id: UUID, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chapter_id": "ch-1",
        "member_id": "m-1",
        "role_id": role_id,
    }
    base.update(overrides)
    return base


def _seed_roster_entry(
    governance_db: PostgresDatabase,
    role_id: UUID,
    *,
    chapter_id: str = "ch-1",
    member_id: str = "m-1",
) -> UUID:
    request = RosterEntryCreate.model_validate(
        _roster_create_kwargs(
            role_id=role_id, chapter_id=chapter_id, member_id=member_id
        )
    )
    with use_audit_context(_make_audit_context()):
        create_roster_entry(governance_db, request)

    with governance_db.connection() as conn, conn.cursor(
        row_factory=dict_row
    ) as cur:
        rows = cur.execute(
            "SELECT id FROM roster_entries "
            "WHERE chapter_id = %s AND member_id = %s AND role_id = %s",
            (chapter_id, member_id, role_id),
        ).fetchall()
    assert len(rows) == 1
    return rows[0]["id"]


def _fetch_status(database_url: str, entry_id: UUID) -> str:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT status FROM roster_entries WHERE id = %s",
            (entry_id,),
        ).fetchone()
    assert row is not None
    return str(row["status"])


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Contract round-trip
# ---------------------------------------------------------------------------


def test_roster_entry_round_trips() -> None:
    """``RosterEntryRead`` must preserve every documented field through
    canonical JSON."""

    original = RosterEntryRead(
        id=uuid4(),
        chapter_id="ch-1",
        member_id="m-1",
        role_id=uuid4(),
        status="active",
        created_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    restored = RosterEntryRead.model_validate_json(original.model_dump_json())

    assert restored.id == original.id
    assert restored.chapter_id == original.chapter_id
    assert restored.member_id == original.member_id
    assert restored.role_id == original.role_id
    assert restored.status == original.status
    assert restored.created_at == original.created_at


# ---------------------------------------------------------------------------
# Persistence + aggregate versioning (AC4)
# ---------------------------------------------------------------------------


def test_create_roster_entry_persists_and_advances_head(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``create_roster_entry`` must persist the row AND advance
    ``aggregate_heads`` to version 1 — AC4's 'versioned + tied to stable
    chapter-role identity' invariant."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        head = conn.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'roster_entry' AND aggregate_id = %s
            """,
            (str(entry_id),),
        ).fetchone()

    assert head is not None
    assert head["current_seq"] == 1


def test_roster_entry_default_status_is_active() -> None:
    """``RosterEntryCreate`` without an explicit status must default to
    ``"active"`` — the canonical entry point into the D8 matrix."""

    request = RosterEntryCreate.model_validate(
        _roster_create_kwargs(role_id=uuid4())
    )
    assert request.status == "active"


# ---------------------------------------------------------------------------
# FK translation (audit F-5)
# ---------------------------------------------------------------------------


def test_roster_entry_fk_to_chapter_role_enforced(
    governance_db: PostgresDatabase,
) -> None:
    """A roster entry whose ``role_id`` does not match a ``chapter_roles`` row
    must surface as a typed ``RosterRoleNotFoundError`` at the service
    boundary, not as a raw psycopg ``ForeignKeyViolation``."""

    request = RosterEntryCreate.model_validate(
        _roster_create_kwargs(role_id=uuid4())
    )

    with use_audit_context(_make_audit_context()):
        with pytest.raises(RosterRoleNotFoundError):
            create_roster_entry(governance_db, request)


# ---------------------------------------------------------------------------
# D8 transition matrix
# ---------------------------------------------------------------------------


def test_transition_roster_status_active_to_on_leave(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``active -> on_leave`` is in the D8 matrix and must succeed."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with use_audit_context(_make_audit_context()):
        transition_roster_status(
            governance_db, entry_id=entry_id, new_status="on_leave"
        )

    assert _fetch_status(governance_dsn, entry_id) == "on_leave"


def test_transition_roster_status_active_to_removed(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``active -> removed`` is in the D8 matrix and must succeed."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with use_audit_context(_make_audit_context()):
        transition_roster_status(
            governance_db, entry_id=entry_id, new_status="removed"
        )

    assert _fetch_status(governance_dsn, entry_id) == "removed"


def test_transition_roster_status_removed_is_terminal(
    governance_db: PostgresDatabase,
) -> None:
    """``removed`` is terminal per D8; any further transition must raise
    ``InvalidRosterStatusTransitionError`` — no silent reactivation."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with use_audit_context(_make_audit_context()):
        transition_roster_status(
            governance_db, entry_id=entry_id, new_status="removed"
        )

        with pytest.raises(InvalidRosterStatusTransitionError):
            transition_roster_status(
                governance_db, entry_id=entry_id, new_status="active"
            )


def test_transition_roster_status_invalid_transition_raises(
    governance_db: PostgresDatabase,
) -> None:
    """A ``new_status`` outside the declared ``RosterStatus`` literal must
    fail Pydantic validation — not hit the DB CHECK and not be silently
    ignored."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with use_audit_context(_make_audit_context()):
        with pytest.raises(ValidationError):
            transition_roster_status(
                governance_db,
                entry_id=entry_id,
                new_status="invalid_status",
            )


def test_transition_roster_status_on_leave_to_under_review_rejected(
    governance_db: PostgresDatabase,
) -> None:
    """``on_leave -> under_review`` is NOT in the D8 matrix; the service must
    reject it with ``InvalidRosterStatusTransitionError``."""

    role_id = _seed_chapter_role(governance_db)
    entry_id = _seed_roster_entry(governance_db, role_id)

    with use_audit_context(_make_audit_context()):
        transition_roster_status(
            governance_db, entry_id=entry_id, new_status="on_leave"
        )

        with pytest.raises(InvalidRosterStatusTransitionError):
            transition_roster_status(
                governance_db,
                entry_id=entry_id,
                new_status="under_review",
            )
