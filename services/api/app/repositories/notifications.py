from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories._claim import claim_due_rows
from app.repositories.db import PostgresDatabase


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
           rendered_embed_json,
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


class NotificationsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_notification_rule(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_notification_rule_on(connection, row=row)

    def update_notification_rule(
        self,
        *,
        rule_id: UUID,
        patch_row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._update_notification_rule_on(
                connection,
                rule_id=rule_id,
                patch_row=patch_row,
            )

    def fetch_notification_rule(self, rule_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_notification_rule_on(connection, rule_id)

    def fetch_notification_rule_for_update(
        self, rule_id: UUID
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_notification_rule_for_update_on(connection, rule_id)

    def list_notification_rules(
        self,
        *,
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_notification_rules_on(
                connection,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )

    def list_enabled_rules_for_event(
        self, *, event_row: dict[str, Any]
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_enabled_rules_for_event_on(
                connection, event_row=event_row
            )

    def insert_notification_envelope_on_conflict_do_nothing(
        self,
        *,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._insert_notification_envelope_on_conflict_do_nothing_on(
                connection,
                row=row,
            )

    def fetch_notification_envelope(self, envelope_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_notification_envelope_on(connection, envelope_id)

    def claim_notification_envelope(
        self,
        *,
        envelope_id: UUID,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._claim_notification_envelope_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                now=now,
                lease_seconds=lease_seconds,
            )

    def mark_envelope_delivered_in_flight(
        self,
        *,
        envelope_id: UUID,
        worker_id: str,
        now: datetime,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._mark_envelope_delivered_in_flight_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                now=now,
            )

    def mark_envelope_delivered(
        self,
        *,
        envelope_id: UUID,
        worker_id: str,
        discord_message_id: str | None,
        delivered_at: datetime,
    ) -> int:
        with self.db.connection() as connection:
            return self._mark_envelope_delivered_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                discord_message_id=discord_message_id,
                delivered_at=delivered_at,
            )

    def mark_envelope_delivery_failure(
        self,
        *,
        envelope_id: UUID,
        worker_id: str,
        now: datetime,
        error_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._mark_envelope_delivery_failure_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                now=now,
                error_payload=error_payload,
            )

    def mark_envelope_ambiguous_failure(
        self,
        *,
        envelope_id: UUID,
        worker_id: str,
        now: datetime,
        error_payload: dict[str, Any],
    ) -> int:
        with self.db.connection() as connection:
            return self._mark_envelope_ambiguous_failure_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                now=now,
                error_payload=error_payload,
            )

    def _insert_notification_rule_on(
        self, connection: Connection[Any], *, row: dict[str, Any]
    ) -> None:
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

    def _update_notification_rule_on(
        self,
        connection: Connection[Any],
        *,
        rule_id: UUID,
        patch_row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
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
            RETURNING updated_at
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
            ).fetchone()

    def _fetch_notification_rule_on(
        self,
        connection: Connection[Any],
        rule_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _RULE_SELECT + " WHERE r.id = %s", (rule_id,)
            ).fetchone()

    def _fetch_notification_rule_for_update_on(
        self,
        connection: Connection[Any],
        rule_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _RULE_SELECT + " WHERE r.id = %s FOR UPDATE OF r",
                (rule_id,),
            ).fetchone()

    def _list_notification_rules_on(
        self,
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

    def _list_enabled_rules_for_event_on(
        self,
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
        query = (
            _RULE_SELECT
            + " WHERE "
            + " AND ".join(predicates)
            + " ORDER BY r.created_at ASC, r.id ASC"
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(query, params).fetchall()

    def _insert_notification_envelope_on_conflict_do_nothing_on(
        self,
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
                    rendered_embed_json,
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                          rendered_embed_json,
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
                    None
                    if row.get("rendered_embed_json") is None
                    else Jsonb(row["rendered_embed_json"]),
                    row["actionable"],
                    row["delivery_status"],
                    row.get("claimed_by"),
                    row.get("claimed_at"),
                    row.get("lease_until"),
                    row["attempts"],
                    row["max_attempts"],
                    None
                    if row.get("last_error_json") is None
                    else Jsonb(row["last_error_json"]),
                    row.get("discord_message_id"),
                    row.get("delivered_at"),
                    row["created_at"],
                    row["updated_at"],
                ),
            ).fetchone()

    def _fetch_notification_envelope_on(
        self,
        connection: Connection[Any],
        envelope_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _ENVELOPE_SELECT + " WHERE id = %s", (envelope_id,)
            ).fetchone()

    def _claim_notification_envelope_on(
        self,
        connection: Connection[Any],
        *,
        envelope_id: UUID,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        rows = claim_due_rows(
            connection,
            table="notification_envelopes",
            primary_key="id",
            worker_id=worker_id,
            batch_size=1,
            now=now,
            lease_seconds=lease_seconds,
            ready_predicate=(
                "id = %s "
                "AND delivery_status = 'pending' "
                "AND attempts < max_attempts "
                "AND (claimed_by IS NULL OR lease_until < %s)"
            ),
            predicate_params=(envelope_id, now),
            order_by="id",
            claim_status=None,
        )
        return rows[0] if rows else None

    def _mark_envelope_delivered_in_flight_on(
        self,
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

    def _mark_envelope_delivered_on(
        self,
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

    def _mark_envelope_delivery_failure_on(
        self,
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

    def _mark_envelope_ambiguous_failure_on(
        self,
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


__all__ = ["NotificationsRepository"]
