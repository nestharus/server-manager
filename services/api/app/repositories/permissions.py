from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


def db_value_to_bit_str(value: Decimal | int | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ValueError(f"expected integer numeric bit mask, got {value!r}")
        return format(value, "f").split(".", 1)[0]
    return str(value)


def _normalize_permission_intent_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["permission_bits"] = db_value_to_bit_str(row.get("permission_bits"))
    normalized["allow_bits"] = db_value_to_bit_str(row.get("allow_bits"))
    normalized["deny_bits"] = db_value_to_bit_str(row.get("deny_bits"))
    if normalized["kind"] == "guild_role":
        normalized.pop("channel_id", None)
        normalized.pop("allow_bits", None)
        normalized.pop("deny_bits", None)
    if normalized["kind"] == "channel_role":
        normalized.pop("permission_bits", None)
    return normalized


def _normalize_permission_drift_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for field in (
        "actual_bits",
        "actual_allow_bits",
        "actual_deny_bits",
        "intended_bits",
        "intended_allow_bits",
        "intended_deny_bits",
    ):
        normalized[field] = db_value_to_bit_str(row.get(field))
    return normalized


def insert_permission_intent(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO permission_intents (
            id,
            kind,
            scope_kind,
            scope_id,
            role_id,
            channel_id,
            permission_bits,
            allow_bits,
            deny_bits,
            reason,
            temporary,
            expires_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["kind"],
            row["scope_kind"],
            row["scope_id"],
            row["role_id"],
            row.get("channel_id"),
            row.get("permission_bits"),
            row.get("allow_bits"),
            row.get("deny_bits"),
            row.get("reason"),
            row["temporary"],
            row.get("expires_at"),
        ),
    )


def fetch_permission_intent(
    connection: Connection[Any],
    intent_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                   permission_bits, allow_bits, deny_bits, reason,
                   temporary, expires_at
            FROM permission_intents
            WHERE id = %s
            """,
            (intent_id,),
        ).fetchone()
    if row is None:
        return None
    return _normalize_permission_intent_row(row)


def update_permission_intent_row(
    connection: Connection[Any],
    *,
    intent_id: UUID,
    row: dict[str, Any],
) -> int:
    cursor = connection.execute(
        """
        UPDATE permission_intents
        SET reason = %s,
            temporary = %s,
            expires_at = %s,
            permission_bits = %s,
            allow_bits = %s,
            deny_bits = %s
        WHERE id = %s
        """,
        (
            row.get("reason"),
            row["temporary"],
            row.get("expires_at"),
            row.get("permission_bits"),
            row.get("allow_bits"),
            row.get("deny_bits"),
            intent_id,
        ),
    )
    return cursor.rowcount


def fetch_permission_drift(
    connection: Connection[Any],
    drift_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT id, permission_intent_id, intent_version,
                   actual_bits, actual_allow_bits, actual_deny_bits,
                   intended_bits, intended_allow_bits, intended_deny_bits,
                   status, detected_at
            FROM permission_drift
            WHERE id = %s
            """,
            (drift_id,),
        ).fetchone()
    if row is None:
        return None
    return _normalize_permission_drift_row(row)


def insert_permission_drift(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO permission_drift (
            id,
            permission_intent_id,
            intent_version,
            actual_bits,
            actual_allow_bits,
            actual_deny_bits,
            intended_bits,
            intended_allow_bits,
            intended_deny_bits,
            status,
            detected_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row.get("permission_intent_id"),
            row.get("intent_version"),
            row.get("actual_bits"),
            row.get("actual_allow_bits"),
            row.get("actual_deny_bits"),
            row.get("intended_bits"),
            row.get("intended_allow_bits"),
            row.get("intended_deny_bits"),
            row["status"],
            row["detected_at"],
        ),
    )


def update_permission_drift_status(
    connection: Connection[Any],
    *,
    drift_id: UUID,
    status: str,
) -> int:
    cursor = connection.execute(
        """
        UPDATE permission_drift
        SET status = %s
        WHERE id = %s
        """,
        (status, drift_id),
    )
    return cursor.rowcount
