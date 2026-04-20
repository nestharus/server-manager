"""Contract tests for WU-007B: chapter role foundation.

Pins the round-trip shape, the ``UNIQUE(chapter_id, ordinal)`` DB
constraint, and the optional-but-real FK to ``chapter_templates.id``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.chapter_roles import ChapterRoleCreate, ChapterRoleRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.chapter_roles import create_chapter_role


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _role_create_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chapter_id": "ch-1",
        "template_id": None,
        "name": "lead",
        "ordinal": 10,
        "triggers_succession": True,
    }
    base.update(overrides)
    return base


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


def test_chapter_role_round_trips() -> None:
    """``ChapterRoleRead`` must preserve every documented field through the
    canonical JSON round-trip."""

    original = ChapterRoleRead(
        id=uuid4(),
        chapter_id="ch-1",
        template_id=uuid4(),
        name="lead",
        ordinal=10,
        triggers_succession=True,
        created_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    restored = ChapterRoleRead.model_validate_json(original.model_dump_json())

    assert restored.id == original.id
    assert restored.chapter_id == original.chapter_id
    assert restored.template_id == original.template_id
    assert restored.name == original.name
    assert restored.ordinal == original.ordinal
    assert restored.triggers_succession == original.triggers_succession
    assert restored.created_at == original.created_at


# ---------------------------------------------------------------------------
# UNIQUE(chapter_id, ordinal) enforcement
# ---------------------------------------------------------------------------


def test_chapter_role_ordinal_unique_per_chapter(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Two roles in the same chapter must not share an ordinal — the unique
    constraint must live at the DB level so concurrent writes can't
    race past a service-only check."""

    first = ChapterRoleCreate.model_validate(_role_create_kwargs())
    with use_audit_context(_make_audit_context()):
        create_chapter_role(governance_db, first)

    second = ChapterRoleCreate.model_validate(
        _role_create_kwargs(name="alt-lead")
    )

    with use_audit_context(_make_audit_context()):
        with pytest.raises(psycopg.errors.UniqueViolation):
            create_chapter_role(governance_db, second)


# ---------------------------------------------------------------------------
# template_id FK behavior (D9)
# ---------------------------------------------------------------------------


def test_chapter_role_template_fk_optional(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``template_id`` must be optional — orphan roles (no template origin)
    are allowed per D9."""

    request = ChapterRoleCreate.model_validate(
        _role_create_kwargs(template_id=None)
    )

    with use_audit_context(_make_audit_context()):
        create_chapter_role(governance_db, request)

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT template_id FROM chapter_roles"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["template_id"] is None


def test_chapter_role_template_fk_enforced_when_set(
    governance_db: PostgresDatabase,
) -> None:
    """A ``template_id`` that does not reference a real template must fail
    at the FK level — no silent orphaning of provisioned roles."""

    request = ChapterRoleCreate.model_validate(
        _role_create_kwargs(template_id=uuid4())
    )

    with use_audit_context(_make_audit_context()):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            create_chapter_role(governance_db, request)
