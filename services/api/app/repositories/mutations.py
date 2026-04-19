from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(slots=True)
class AggregateHeadRow:
    aggregate_type: str
    aggregate_id: int
    current_seq: int
    latest_change_id: int | None


def get_head_for_update(
    connection: Connection[Any],
    *,
    aggregate_type: str,
    aggregate_id: int,
) -> AggregateHeadRow | None:
    row = connection.execute(
        """
        SELECT aggregate_type, aggregate_id, current_seq, latest_change_id
        FROM aggregate_heads
        WHERE aggregate_type = %s AND aggregate_id = %s
        FOR UPDATE
        """,
        (aggregate_type, aggregate_id),
    ).fetchone()

    if row is None:
        return None

    return AggregateHeadRow(
        aggregate_type=str(row[0]),
        aggregate_id=int(row[1]),
        current_seq=int(row[2]),
        latest_change_id=None if row[3] is None else int(row[3]),
    )


def insert_action(
    connection: Connection[Any],
    *,
    action_type: str,
    aggregate_type: str,
    aggregate_id: int,
    actor_kind: str,
    actor_id: str,
    request_surface: str,
    request_json: dict[str, object],
    status: str,
    reason_text: str | None = None,
    error_metadata: dict[str, object] | None = None,
) -> int:
    row = connection.execute(
        """
        INSERT INTO activity_actions (
            action_type,
            aggregate_type,
            aggregate_id,
            actor_kind,
            actor_id,
            request_surface,
            request_json,
            status,
            reason_text,
            error_metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            action_type,
            aggregate_type,
            aggregate_id,
            actor_kind,
            actor_id,
            request_surface,
            Jsonb(request_json),
            status,
            reason_text,
            None if error_metadata is None else Jsonb(error_metadata),
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError("failed to insert activity action")

    return int(row[0])


def insert_state_change(
    connection: Connection[Any],
    *,
    action_id: int,
    aggregate_type: str,
    aggregate_id: int,
    aggregate_seq: int,
    change_type: str,
    payload_json: dict[str, Any],
    diff_json: dict[str, Any] | None,
) -> int:
    row = connection.execute(
        """
        INSERT INTO activity_state_changes (
            action_id,
            aggregate_type,
            aggregate_id,
            aggregate_seq,
            change_type,
            payload_json,
            diff_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            action_id,
            aggregate_type,
            aggregate_id,
            aggregate_seq,
            change_type,
            Jsonb(payload_json),
            None if diff_json is None else Jsonb(diff_json),
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError("failed to insert activity state change")

    return int(row[0])


def advance_head(
    connection: Connection[Any],
    *,
    aggregate_type: str,
    aggregate_id: int,
    new_version: int,
    latest_change_id: int,
) -> None:
    cursor = connection.execute(
        """
        UPDATE aggregate_heads
        SET current_seq = %s, latest_change_id = %s
        WHERE aggregate_type = %s AND aggregate_id = %s
        """,
        (new_version, latest_change_id, aggregate_type, aggregate_id),
    )
    if cursor.rowcount != 1:
        raise RuntimeError(
            f"advance_head matched {cursor.rowcount} rows for "
            f"{aggregate_type}#{aggregate_id}; expected 1"
        )
