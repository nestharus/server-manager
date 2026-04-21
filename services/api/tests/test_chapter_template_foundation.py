"""Contract tests for WU-007A: chapter template foundation (AC3).

Pins the three-part JSONB structure (channel_structure, role_structure,
default_permission_intents), the nested Pydantic validators, the
immutable-read semantics, and the explicit ``schema_version`` gate so
future shape changes fail loudly instead of being silently mis-parsed.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChannelSpec,
    ChapterTemplateCreate,
    ChapterTemplateRead,
    DefaultIntentSpec,
    RoleSpec,
    TemplateSchemaVersionMismatchError,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.chapter_templates import (
    create_chapter_template,
    read_chapter_template,
)


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _channel_specs() -> list[dict[str, Any]]:
    return [
        {"name": "general", "type": "text", "topic": "General chat"},
        {"name": "lounge", "type": "voice"},
    ]


def _role_specs() -> list[dict[str, Any]]:
    return [
        {"name": "lead", "ordinal": 10, "triggers_succession": True},
        {"name": "member", "ordinal": 20, "triggers_succession": False},
    ]


def _default_intents() -> list[dict[str, Any]]:
    return [
        {
            "role_name": "lead",
            "kind": "guild_role",
            "permission_bits": "2048",
            "temporary": False,
        },
        {
            "role_name": "member",
            "kind": "channel_role",
            "allow_bits": "1024",
            "deny_bits": "0",
            "channel_name": "general",
            "temporary": False,
        },
    ]


def _template_create_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Chapter Template A",
        "schema_version": CURRENT_TEMPLATE_SCHEMA_VERSION,
        "channel_structure": _channel_specs(),
        "role_structure": _role_specs(),
        "default_permission_intents": _default_intents(),
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
# Full-shape JSON round-trip (AC3)
# ---------------------------------------------------------------------------


def test_chapter_template_round_trips_to_json() -> None:
    """A fully populated ``ChapterTemplateRead`` must round-trip through the
    canonical ``model_dump(mode='json')`` form with all three nested
    structures preserved."""

    from datetime import UTC, datetime

    original = ChapterTemplateRead(
        id=uuid4(),
        template_family_id=uuid4(),
        version=1,
        name="Chapter Template A",
        schema_version=CURRENT_TEMPLATE_SCHEMA_VERSION,
        channel_structure=[ChannelSpec.model_validate(c) for c in _channel_specs()],
        role_structure=[RoleSpec.model_validate(r) for r in _role_specs()],
        default_permission_intents=[
            DefaultIntentSpec.model_validate(d) for d in _default_intents()
        ],
        created_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    restored = ChapterTemplateRead.model_validate_json(original.model_dump_json())

    assert restored.id == original.id
    assert restored.name == original.name
    assert restored.schema_version == original.schema_version
    assert restored.channel_structure == original.channel_structure
    assert restored.role_structure == original.role_structure
    assert restored.default_permission_intents == original.default_permission_intents
    assert restored.created_at == original.created_at


# ---------------------------------------------------------------------------
# Nested spec validators
# ---------------------------------------------------------------------------


def test_channel_spec_validates_type() -> None:
    """``ChannelSpec.type`` must be constrained to the documented literal
    set — arbitrary Discord channel types don't belong in phase 0."""

    with pytest.raises(ValidationError):
        ChannelSpec.model_validate({"name": "x", "type": "invalid"})


def test_role_spec_validates_ordinal() -> None:
    """``RoleSpec.ordinal`` must reject negative numbers; ordinals are a
    non-negative ordering key."""

    with pytest.raises(ValidationError):
        RoleSpec.model_validate(
            {"name": "lead", "ordinal": -1, "triggers_succession": False}
        )


def test_default_intent_spec_guild_role_shape() -> None:
    """A ``guild_role`` default must carry ``permission_bits`` and no
    channel-role fields."""

    spec = DefaultIntentSpec.model_validate(
        {
            "role_name": "lead",
            "kind": "guild_role",
            "permission_bits": "2048",
            "temporary": False,
        }
    )
    assert spec.kind == "guild_role"
    assert spec.permission_bits == "2048"


def test_default_intent_spec_channel_role_shape() -> None:
    """A ``channel_role`` default must carry ``allow_bits``, ``deny_bits``,
    and ``channel_name``."""

    spec = DefaultIntentSpec.model_validate(
        {
            "role_name": "member",
            "kind": "channel_role",
            "allow_bits": "1024",
            "deny_bits": "0",
            "channel_name": "general",
            "temporary": False,
        }
    )
    assert spec.kind == "channel_role"
    assert spec.allow_bits == "1024"
    assert spec.deny_bits == "0"
    assert spec.channel_name == "general"


def test_default_intent_spec_temporary_requires_expires_in_days() -> None:
    """``temporary=True`` must require ``expires_in_days`` to be set."""

    with pytest.raises(ValidationError):
        DefaultIntentSpec.model_validate(
            {
                "role_name": "lead",
                "kind": "guild_role",
                "permission_bits": "2048",
                "temporary": True,
                "expires_in_days": None,
            }
        )


# ---------------------------------------------------------------------------
# Persistence + schema-version behavior
# ---------------------------------------------------------------------------


def test_create_chapter_template_persists_row(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``create_chapter_template`` must insert a ``chapter_templates`` row
    via ``mutate_entity()``."""

    request = ChapterTemplateCreate.model_validate(_template_create_kwargs())

    with use_audit_context(_make_audit_context()):
        create_chapter_template(governance_db, request)

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT id, template_family_id, version, name, schema_version,
                   channel_structure, role_structure, default_permission_intents
            FROM chapter_templates
            """
        ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row["template_family_id"] == row["id"]
    assert row["version"] == 1
    assert row["name"] == "Chapter Template A"
    assert row["schema_version"] == CURRENT_TEMPLATE_SCHEMA_VERSION
    assert isinstance(row["channel_structure"], list)
    assert isinstance(row["role_structure"], list)
    assert isinstance(row["default_permission_intents"], list)


def test_chapter_template_is_immutable() -> None:
    """Templates are immutable in SLICE-003: the service module must expose
    no ``update_chapter_template`` surface."""

    import app.services.chapter_templates as svc

    assert not hasattr(svc, "update_chapter_template"), (
        "chapter templates must be immutable in SLICE-003 "
        "(see proposal §3 WU-007A)"
    )


def test_template_schema_version_matches_current(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """A freshly created template must carry the currently-declared
    ``schema_version`` constant; any drift indicates a migration without a
    contract bump."""

    request = ChapterTemplateCreate.model_validate(_template_create_kwargs())
    with use_audit_context(_make_audit_context()):
        create_chapter_template(governance_db, request)

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT schema_version FROM chapter_templates"
        ).fetchone()
    assert row is not None
    assert row["schema_version"] == CURRENT_TEMPLATE_SCHEMA_VERSION


def test_read_template_with_stale_schema_raises(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Reading a row stamped with a ``schema_version`` different from the
    current constant must raise ``TemplateSchemaVersionMismatchError`` so
    stale rows fail loudly instead of being silently mis-parsed."""

    import json

    stale_id = uuid4()
    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO chapter_templates (
                id, template_family_id, version, name, schema_version,
                channel_structure, role_structure, default_permission_intents
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                stale_id,
                stale_id,
                1,
                "Stale Template",
                99,
                json.dumps(_channel_specs()),
                json.dumps(_role_specs()),
                json.dumps(_default_intents()),
            ),
        )

    with pytest.raises(TemplateSchemaVersionMismatchError):
        read_chapter_template(governance_db, stale_id)
