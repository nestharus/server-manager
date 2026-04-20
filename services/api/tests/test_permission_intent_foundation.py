"""Contract tests for WU-006A: permission intent foundation (AC1 + AC2).

Pins the discriminated-union contract, the shared ``DecimalBitString``
validator, the temporal invariant on ``temporary``/``expires_at``, the
``validated_update`` helper, the aggregate-id formatter, and the
``mutate_entity()``-based persistence path.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.base import AGGREGATE_SCOPE_MISSING, validated_update
from app.contracts.mutations import StaleMutationError
from app.contracts.permissions import (
    ChannelRolePermissionIntent,
    GuildRolePermissionIntent,
    PermissionIntentCreate,
    PermissionIntentRead,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.permissions import (
    build_permission_intent_aggregate_id,
    create_permission_intent,
    read_permission_intent,
    update_permission_intent,
)


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(days=1)


def _guild_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": uuid4(),
        "kind": "guild_role",
        "scope_kind": "chapter",
        "scope_id": "ch-1",
        "role_id": "R1",
        "permission_bits": "123",
        "reason": None,
        "temporary": False,
        "expires_at": None,
    }
    base.update(overrides)
    return base


def _channel_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": uuid4(),
        "kind": "channel_role",
        "scope_kind": "chapter",
        "scope_id": "ch-1",
        "role_id": "R1",
        "channel_id": "C1",
        "allow_bits": "16",
        "deny_bits": "8",
        "reason": None,
        "temporary": False,
        "expires_at": None,
    }
    base.update(overrides)
    return base


def _create_guild_intent(scope_id: str | None = "ch-1") -> PermissionIntentCreate:
    return PermissionIntentCreate.model_validate(
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


def _fetch_permission_intent_row(
    database_url: str, intent_id: UUID
) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                   permission_bits, allow_bits, deny_bits, reason,
                   temporary, expires_at
            FROM permission_intents
            WHERE id = %s
            """,
            (intent_id,),
        ).fetchone()


def _fetch_aggregate_head(
    database_url: str, aggregate_id: str
) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'permission_intent' AND aggregate_id = %s
            """,
            (aggregate_id,),
        ).fetchone()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Discriminated-union JSON round-trip (AC1)
# ---------------------------------------------------------------------------


def test_guild_role_intent_round_trips_to_json() -> None:
    """``GuildRolePermissionIntent`` must round-trip through the canonical
    ``model_dump(mode='json')`` form via ``PermissionIntentRead``."""

    intent = GuildRolePermissionIntent(**_guild_kwargs())
    serialized = intent.model_dump(mode="json")
    assert serialized["kind"] == "guild_role"

    restored = PermissionIntentRead.model_validate(serialized)

    assert restored.kind == "guild_role"
    assert restored.id == intent.id
    assert restored.scope_kind == intent.scope_kind
    assert restored.scope_id == intent.scope_id
    assert restored.role_id == intent.role_id
    assert restored.permission_bits == intent.permission_bits
    assert restored.reason == intent.reason
    assert restored.temporary == intent.temporary
    assert restored.expires_at == intent.expires_at


def test_channel_role_intent_round_trips_to_json() -> None:
    """``ChannelRolePermissionIntent`` must round-trip through the canonical
    ``model_dump(mode='json')`` form via ``PermissionIntentRead``."""

    intent = ChannelRolePermissionIntent(**_channel_kwargs())
    serialized = intent.model_dump(mode="json")
    assert serialized["kind"] == "channel_role"

    restored = PermissionIntentRead.model_validate(serialized)

    assert restored.kind == "channel_role"
    assert restored.id == intent.id
    assert restored.scope_kind == intent.scope_kind
    assert restored.scope_id == intent.scope_id
    assert restored.role_id == intent.role_id
    assert restored.channel_id == intent.channel_id
    assert restored.allow_bits == intent.allow_bits
    assert restored.deny_bits == intent.deny_bits


def test_discriminated_union_parses_by_kind() -> None:
    """``PermissionIntentRead.model_validate(...)`` must dispatch on the
    ``kind`` discriminator and return the concrete variant."""

    guild = PermissionIntentRead.model_validate(_guild_kwargs())
    assert isinstance(guild, GuildRolePermissionIntent)
    assert guild.kind == "guild_role"

    channel = PermissionIntentRead.model_validate(_channel_kwargs())
    assert isinstance(channel, ChannelRolePermissionIntent)
    assert channel.kind == "channel_role"


def test_unknown_kind_rejected() -> None:
    """Any ``kind`` outside the declared discriminator values must fail at
    the union boundary — not silently parse to a default variant."""

    data = _guild_kwargs()
    data["kind"] = "member_role"
    with pytest.raises(ValidationError):
        PermissionIntentRead.model_validate(data)


# ---------------------------------------------------------------------------
# Per-variant shape invariants
# ---------------------------------------------------------------------------


def test_guild_role_rejects_channel_fields() -> None:
    """``GuildRolePermissionIntent`` must reject the channel-only
    ``channel_id`` field even via kwargs — the variant shape is closed."""

    kwargs = _guild_kwargs()
    kwargs["channel_id"] = "C1"
    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(**kwargs)


def test_channel_role_requires_both_masks() -> None:
    """``ChannelRolePermissionIntent`` must require both ``allow_bits`` and
    ``deny_bits`` to be present."""

    kwargs = _channel_kwargs()
    kwargs["deny_bits"] = None
    with pytest.raises(ValidationError):
        ChannelRolePermissionIntent(**kwargs)


# ---------------------------------------------------------------------------
# Temporal invariant (AC2)
# ---------------------------------------------------------------------------


def test_temporary_requires_expires_at() -> None:
    """``temporary=True`` requires ``expires_at`` to be set; missing
    expiration is a contract violation at construction time."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(
            **_guild_kwargs(temporary=True, expires_at=None)
        )


def test_non_temporary_forbids_expires_at() -> None:
    """``temporary=False`` forbids ``expires_at``; a stray timestamp on a
    permanent intent is a contract violation."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(
            **_guild_kwargs(temporary=False, expires_at=_future())
        )


# ---------------------------------------------------------------------------
# validated_update helper (D10 + AC2)
# ---------------------------------------------------------------------------


def test_validated_update_rejects_expires_at_only_patch_on_non_temporary() -> None:
    """Applying ``{"expires_at": <ts>}`` to a non-temporary intent must fail
    validation; bare ``model_copy(update=...)`` would silently accept it."""

    current = GuildRolePermissionIntent(
        **_guild_kwargs(temporary=False, expires_at=None)
    )
    with pytest.raises(ValidationError):
        validated_update(current, {"expires_at": _future()})


def test_validated_update_accepts_clear_temporary_patch() -> None:
    """Clearing ``temporary`` back to ``False`` while also nulling
    ``expires_at`` is the canonical shape-preserving transition."""

    future_ts = _future()
    current = GuildRolePermissionIntent(
        **_guild_kwargs(temporary=True, expires_at=future_ts)
    )
    updated = validated_update(
        current, {"temporary": False, "expires_at": None}
    )
    assert updated.temporary is False
    assert updated.expires_at is None
    assert updated.kind == "guild_role"


# ---------------------------------------------------------------------------
# DecimalBitString validator
# ---------------------------------------------------------------------------


def test_decimal_bit_string_validator_rejects_empty_string() -> None:
    """The decimal-bit-string alias must reject an empty string — only
    ``None`` represents 'missing' at the contract boundary."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(**_guild_kwargs(permission_bits=""))


def test_decimal_bit_string_validator_rejects_leading_zero() -> None:
    """Leading zeros are not canonical decimal form for a mask; only the
    single digit ``"0"`` is allowed."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(**_guild_kwargs(permission_bits="007"))


def test_decimal_bit_string_validator_rejects_negative() -> None:
    """Permission masks are non-negative; a leading ``-`` must fail."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(**_guild_kwargs(permission_bits="-1"))


def test_decimal_bit_string_validator_accepts_zero() -> None:
    """``"0"`` is the canonical all-bits-clear mask and must be accepted."""

    intent = GuildRolePermissionIntent(**_guild_kwargs(permission_bits="0"))
    assert intent.permission_bits == "0"


def test_decimal_bit_string_validator_accepts_large_mask() -> None:
    """Masks beyond 63 bits must round-trip — the contract's headroom claim
    goes well past BIGINT."""

    big = str(1 << 120)
    intent = GuildRolePermissionIntent(**_guild_kwargs(permission_bits=big))
    assert intent.permission_bits == big


# ---------------------------------------------------------------------------
# Non-empty identifier invariants (shortcut F2)
# ---------------------------------------------------------------------------


def test_scope_id_empty_string_rejected() -> None:
    """Empty-string ``scope_id`` must be rejected at contract ingress so it
    cannot collide with the ``None`` sentinel at the aggregate-id boundary."""

    with pytest.raises(ValidationError):
        GuildRolePermissionIntent(**_guild_kwargs(scope_id=""))


def test_channel_id_empty_string_rejected() -> None:
    """Empty-string ``channel_id`` must be rejected on the channel variant
    for the same reason as ``scope_id``."""

    with pytest.raises(ValidationError):
        ChannelRolePermissionIntent(**_channel_kwargs(channel_id=""))


# ---------------------------------------------------------------------------
# Persistence + aggregate-head advancement (AC1)
# ---------------------------------------------------------------------------


def test_create_permission_intent_persists_row_and_advances_head(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``create_permission_intent`` must insert a ``permission_intents`` row
    and advance ``aggregate_heads`` to version 1 for the intent's
    canonical aggregate id."""

    request = _create_guild_intent(scope_id="ch-1")

    with use_audit_context(_make_audit_context()):
        result = create_permission_intent(governance_db, request)

    assert result.version == 1
    assert result.etag == '"1"'

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT id, kind, scope_kind, scope_id, role_id, channel_id, "
            "permission_bits, temporary, expires_at "
            "FROM permission_intents"
        ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "guild_role"
    assert row["scope_kind"] == "chapter"
    assert row["scope_id"] == "ch-1"
    assert row["role_id"] == "R1"
    assert row["channel_id"] is None
    assert row["temporary"] is False

    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind="chapter",
        scope_id="ch-1",
        role_id="R1",
        channel_id=None,
    )
    head = _fetch_aggregate_head(governance_dsn, aggregate_id)
    assert head is not None
    assert head["current_seq"] == 1


def test_update_permission_intent_requires_expected_version(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """A stale ``expected_version`` on update must raise ``StaleMutationError``
    — OCC is enforced through ``mutate_entity()``."""

    request = _create_guild_intent(scope_id="ch-1")
    with use_audit_context(_make_audit_context()):
        create_result = create_permission_intent(governance_db, request)
    assert create_result.version == 1

    intent_id = _only_intent_id(governance_dsn)

    with use_audit_context(_make_audit_context()):
        with pytest.raises(StaleMutationError):
            update_permission_intent(
                governance_db,
                intent_id,
                expected_version=0,
                patch={"reason": "late update"},
            )


def _only_intent_id(database_url: str) -> UUID:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute("SELECT id FROM permission_intents").fetchall()
    assert len(rows) == 1
    return rows[0]["id"]


# ---------------------------------------------------------------------------
# Aggregate-id helper (shortcut F-4 + F-9)
# ---------------------------------------------------------------------------


def test_build_permission_intent_aggregate_id_byte_for_byte() -> None:
    """The helper must produce the exact documented string so downstream
    callers never hand-format it."""

    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind="chapter",
        scope_id=None,
        role_id="R1",
        channel_id="C1",
    )
    assert aggregate_id == "permission_intent|chapter||role:R1|channel:C1"


def test_build_permission_intent_aggregate_id_no_collision() -> None:
    """``(scope_id=None, channel_id=X)`` and ``(scope_id=X, channel_id=None)``
    must produce distinct aggregate ids — the shared empty-string sentinel
    must not swallow positional meaning."""

    a = build_permission_intent_aggregate_id(
        scope_kind="chapter",
        scope_id=None,
        role_id="R1",
        channel_id="X",
    )
    b = build_permission_intent_aggregate_id(
        scope_kind="chapter",
        scope_id="X",
        role_id="R1",
        channel_id=None,
    )
    assert a != b
    # Sanity: the shared sentinel is indeed the empty string (shortcut F1).
    assert AGGREGATE_SCOPE_MISSING == ""
