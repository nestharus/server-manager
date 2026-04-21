from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_RULE_SELECT = """
    SELECT r.id,
           r.trigger_json,
           r.scope_kind,
           r.scope_id,
           r.recipients_json,
           r.channel,
           r.template_json,
           r.actionable,
           r.grouping,
           r.enabled,
           r.created_at,
           r.updated_at,
           h.current_seq AS version
    FROM notification_rules AS r
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'notification_rule'
     AND h.aggregate_id = r.id::text
"""

_ENVELOPE_SELECT = """
    SELECT id,
           rule_id,
           rule_version,
           source_event_id,
           root_correlation_id,
           causation_id,
           grouping,
           recipient_key,
           recipient_discord_id,
           recipient_display,
           channel,
           destination_channel_id,
           template_snapshot_json,
           rendered_title,
           rendered_body,
           actionable,
           delivery_status,
           claimed_by,
           claimed_at,
           lease_until,
           attempts,
           max_attempts,
           last_error_json,
           discord_message_id,
           delivered_at,
           created_at,
           updated_at
    FROM notification_envelopes
"""


def insert_notification_rule(connection: Connection[Any], *, row: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO notification_rules (
            id,
            trigger_json,
            scope_kind,
            scope_id,
            recipients_json,
            channel,
            template_json,
            actionable,
            grouping,
            enabled
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            Jsonb(row["trigger_json"]),
            row["scope_kind"],
            row.get("scope_id"),
            Jsonb(row["recipients_json"]),
            row["channel"],
            Jsonb(row["template_json"]),
            row["actionable"],
            row["grouping"],
            row["enabled"],
        ),
    )


def update_notification_rule(
    connection: Connection[Any],
    *,
    rule_id: UUID,
    patch_row: dict[str, Any],
) -> int:
    cursor = connection.execute(
        """
        UPDATE notification_rules
        SET trigger_json = %s,
            scope_kind = %s,
            scope_id = %s,
            recipients_json = %s,
            channel = %s,
            template_json = %s,
            actionable = %s,
            grouping = %s,
            enabled = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            Jsonb(patch_row["trigger_json"]),
            patch_row["scope_kind"],
            patch_row.get("scope_id"),
            Jsonb(patch_row["recipients_json"]),
            patch_row["channel"],
            Jsonb(patch_row["template_json"]),
            patch_row["actionable"],
            patch_row["grouping"],
            patch_row["enabled"],
            rule_id,
        ),
    )
    return cursor.rowcount


def fetch_notification_rule(
    connection: Connection[Any],
    rule_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(_RULE_SELECT + " WHERE r.id = %s", (rule_id,)).fetchone()


def fetch_notification_rule_for_update(
    connection: Connection[Any],
    rule_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _RULE_SELECT + " WHERE r.id = %s FOR UPDATE OF r",
            (rule_id,),
        ).fetchone()


def list_notification_rules(
    connection: Connection[Any],
    *,
    scope_kind: str | None = None,
    scope_id: str | None = None,
) -> list[dict[str, Any]]:
    predicates: list[str] = []
    params: list[Any] = []
    if scope_kind is not None:
        predicates.append("r.scope_kind = %s")
        params.append(scope_kind)
    if scope_id is not None:
        predicates.append("r.scope_id = %s")
        params.append(scope_id)
    query = _RULE_SELECT
    if predicates:
        query += " WHERE " + " AND ".join(predicates)
    query += " ORDER BY r.created_at ASC, r.id ASC"
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()


def list_enabled_rules_for_event(
    connection: Connection[Any],
    *,
    event_row: dict[str, Any],
) -> list[dict[str, Any]]:
    event_scope_kind = event_row.get("scope_kind")
    event_scope_id = event_row.get("scope_id")
    predicates = ["r.enabled = TRUE"]
    params: list[Any] = []
    if event_scope_kind is None:
        predicates.append("r.scope_kind = 'global'")
    else:
        predicates.append(
            """
            (
                r.scope_kind = 'global'
                OR (r.scope_kind = %s AND r.scope_id IS NOT DISTINCT FROM %s)
            )
            """
        )
        params.extend([event_scope_kind, event_scope_id])
    query = _RULE_SELECT + " WHERE " + " AND ".join(predicates) + " ORDER BY r.created_at ASC, r.id ASC"
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()


def insert_notification_envelope_on_conflict_do_nothing(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            INSERT INTO notification_envelopes (
                id,
                rule_id,
                rule_version,
                source_event_id,
                root_correlation_id,
                causation_id,
                grouping,
                recipient_key,
                recipient_discord_id,
                recipient_display,
                channel,
                destination_channel_id,
                template_snapshot_json,
                rendered_title,
                rendered_body,
                actionable,
                delivery_status,
                claimed_by,
                claimed_at,
                lease_until,
                attempts,
                max_attempts,
                last_error_json,
                discord_message_id,
                delivered_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
            RETURNING id,
                      rule_id,
                      rule_version,
                      source_event_id,
                      root_correlation_id,
                      causation_id,
                      grouping,
                      recipient_key,
                      recipient_discord_id,
                      recipient_display,
                      channel,
                      destination_channel_id,
                      template_snapshot_json,
                      rendered_title,
                      rendered_body,
                      actionable,
                      delivery_status,
                      claimed_by,
                      claimed_at,
                      lease_until,
                      attempts,
                      max_attempts,
                      last_error_json,
                      discord_message_id,
                      delivered_at,
                      created_at,
                      updated_at
            """,
            (
                row["id"],
                row["rule_id"],
                row["rule_version"],
                row["source_event_id"],
                row["root_correlation_id"],
                row.get("causation_id"),
                row["grouping"],
                row["recipient_key"],
                row.get("recipient_discord_id"),
                row["recipient_display"],
                row["channel"],
                row.get("destination_channel_id"),
                Jsonb(row["template_snapshot_json"]),
                row["rendered_title"],
                row["rendered_body"],
                row["actionable"],
                row["delivery_status"],
                row.get("claimed_by"),
                row.get("claimed_at"),
                row.get("lease_until"),
                row["attempts"],
                row["max_attempts"],
                None if row.get("last_error_json") is None else Jsonb(row["last_error_json"]),
                row.get("discord_message_id"),
                row.get("delivered_at"),
                row["created_at"],
                row["updated_at"],
            ),
        ).fetchone()


def fetch_notification_envelope(
    connection: Connection[Any],
    envelope_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(_ENVELOPE_SELECT + " WHERE id = %s", (envelope_id,)).fetchone()


def claim_notification_envelope(
    connection: Connection[Any],
    *,
    envelope_id: UUID,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> dict[str, Any] | None:
    lease_until = now + timedelta(seconds=lease_seconds)
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            WITH claimable AS (
                SELECT id
                FROM notification_envelopes
                WHERE id = %s
                  AND delivery_status = 'pending'
                  AND attempts < max_attempts
                  AND (claimed_by IS NULL OR lease_until < %s)
                FOR UPDATE SKIP LOCKED
            )
            UPDATE notification_envelopes AS target
            SET claimed_by = %s,
                claimed_at = %s,
                lease_until = %s,
                updated_at = %s
            FROM claimable
            WHERE target.id = claimable.id
            RETURNING target.*
            """,
            (envelope_id, now, worker_id, now, lease_until, now),
        ).fetchone()


def mark_envelope_delivered_in_flight(
    connection: Connection[Any],
    *,
    envelope_id: UUID,
    worker_id: str,
    now: datetime,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE notification_envelopes
            SET delivery_status = 'delivered_in_flight',
                updated_at = %s
            WHERE id = %s
              AND claimed_by = %s
              AND delivery_status = 'pending'
            RETURNING *
            """,
            (now, envelope_id, worker_id),
        ).fetchone()


def mark_envelope_delivered(
    connection: Connection[Any],
    *,
    envelope_id: UUID,
    worker_id: str,
    discord_message_id: str | None,
    delivered_at: datetime,
) -> int:
    cursor = connection.execute(
        """
        UPDATE notification_envelopes
        SET delivery_status = 'delivered',
            discord_message_id = %s,
            delivered_at = %s,
            claimed_by = NULL,
            claimed_at = NULL,
            lease_until = NULL,
            updated_at = %s
        WHERE id = %s
          AND claimed_by = %s
        """,
        (discord_message_id, delivered_at, delivered_at, envelope_id, worker_id),
    )
    return cursor.rowcount


def mark_envelope_delivery_failure(
    connection: Connection[Any],
    *,
    envelope_id: UUID,
    worker_id: str,
    now: datetime,
    error_payload: dict[str, Any],
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE notification_envelopes
            SET attempts = attempts + 1,
                last_error_json = %s,
                delivery_status = CASE
                    WHEN attempts + 1 >= max_attempts THEN 'failed'
                    ELSE 'pending'
                END,
                claimed_by = NULL,
                claimed_at = NULL,
                lease_until = NULL,
                updated_at = %s
            WHERE id = %s
              AND claimed_by = %s
            RETURNING *
            """,
            (Jsonb(error_payload), now, envelope_id, worker_id),
        ).fetchone()


def mark_envelope_ambiguous_failure(
    connection: Connection[Any],
    *,
    envelope_id: UUID,
    worker_id: str,
    now: datetime,
    error_payload: dict[str, Any],
) -> int:
    cursor = connection.execute(
        """
        UPDATE notification_envelopes
        SET delivery_status = 'delivered_in_flight',
            last_error_json = %s,
            lease_until = NULL,
            updated_at = %s
        WHERE id = %s
          AND claimed_by = %s
        """,
        (Jsonb(error_payload), now, envelope_id, worker_id),
    )
    return cursor.rowcount
