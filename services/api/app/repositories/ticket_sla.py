from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


_TRIGGER_SELECT = """
    SELECT id,
           ticket_id,
           rule_key,
           threshold_seconds,
           consequence,
           target_state,
           state,
           state_entered_at,
           elapsed_seconds,
           applied_at,
           effect_summary_json,
           created_at
    FROM ticket_sla_triggers
"""


class TicketSlaRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def find_due_tickets(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._find_due_tickets_on(connection, now=now, limit=limit)

    def _find_due_tickets_on(
        self,
        connection: Connection[Any],
        *,
        now: datetime,  # noqa: ARG002 - reserved for stable evaluator query signatures
        limit: int,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT t.id,
                       t.category_id,
                       t.category_version,
                       t.category_snapshot,
                       t.reporter_id,
                       t.subject_id,
                       t.state,
                       t.priority,
                       t.owner_id,
                       t.resolution,
                       t.terminal_at,
                       t.created_at,
                       t.updated_at,
                       h.current_seq AS version
                FROM tickets AS t
                JOIN aggregate_heads AS h
                  ON h.aggregate_type = 'ticket'
                 AND h.aggregate_id = t.id::text
                WHERE t.terminal_at IS NULL
                  AND jsonb_typeof(t.category_snapshot #> '{sla_rules,rules}') = 'array'
                  AND jsonb_array_length(t.category_snapshot #> '{sla_rules,rules}') > 0
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(t.category_snapshot #> '{sla_rules,rules}') AS rule(value)
                      WHERE jsonb_typeof(rule.value->'states') = 'array'
                        AND (rule.value->'states') ? t.state
                  )
                ORDER BY t.created_at ASC, t.id ASC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

    def find_last_transition_to_state(
        self,
        *,
        ticket_id: UUID,
        state: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._find_last_transition_to_state_on(
                connection,
                ticket_id=ticket_id,
                state=state,
            )

    def _find_last_transition_to_state_on(
        self,
        connection: Connection[Any],
        *,
        ticket_id: UUID,
        state: str,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id,
                       ticket_id,
                       aggregate_seq,
                       action,
                       from_state,
                       to_state,
                       recorded_at
                FROM ticket_transitions
                WHERE ticket_id = %s
                  AND to_state = %s
                ORDER BY aggregate_seq DESC
                LIMIT 1
                """,
                (ticket_id, state),
            ).fetchone()

    def get_existing_triggers(self, *, ticket_id: UUID) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._get_existing_triggers_on(connection, ticket_id=ticket_id)

    def _get_existing_triggers_on(
        self,
        connection: Connection[Any],
        *,
        ticket_id: UUID,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _TRIGGER_SELECT
                + """
                WHERE ticket_id = %s
                ORDER BY applied_at ASC, id ASC
                """,
                (ticket_id,),
            ).fetchall()

    def insert_trigger(self, *, row: dict[str, Any]) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._insert_trigger_on(connection, row=row)

    def _insert_trigger_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                INSERT INTO ticket_sla_triggers (
                    id,
                    ticket_id,
                    rule_key,
                    threshold_seconds,
                    consequence,
                    target_state,
                    state,
                    state_entered_at,
                    elapsed_seconds,
                    effect_summary_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT uq_ticket_sla_triggers__ticket_rule_threshold
                DO NOTHING
                RETURNING id,
                          ticket_id,
                          rule_key,
                          threshold_seconds,
                          consequence,
                          target_state,
                          state,
                          state_entered_at,
                          elapsed_seconds,
                          applied_at,
                          effect_summary_json,
                          created_at
                """,
                (
                    row["id"],
                    row["ticket_id"],
                    row["rule_key"],
                    row["threshold_seconds"],
                    row["consequence"],
                    row.get("target_state"),
                    row["state"],
                    row["state_entered_at"],
                    row["elapsed_seconds"],
                    Jsonb(row.get("effect_summary_json", {})),
                ),
            ).fetchone()

    def update_trigger_effect_summary(
        self,
        *,
        trigger_id: UUID,
        effect_summary_json: dict[str, Any],
    ) -> dict[str, Any]:
        with self.db.connection() as connection:
            return self._update_trigger_effect_summary_on(
                connection,
                trigger_id=trigger_id,
                effect_summary_json=effect_summary_json,
            )

    def _update_trigger_effect_summary_on(
        self,
        connection: Connection[Any],
        *,
        trigger_id: UUID,
        effect_summary_json: dict[str, Any],
    ) -> dict[str, Any]:
        with connection.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                UPDATE ticket_sla_triggers
                SET effect_summary_json = %s
                WHERE id = %s
                RETURNING id,
                          ticket_id,
                          rule_key,
                          threshold_seconds,
                          consequence,
                          target_state,
                          state,
                          state_entered_at,
                          elapsed_seconds,
                          applied_at,
                          effect_summary_json,
                          created_at
                """,
                (Jsonb(effect_summary_json), trigger_id),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"ticket SLA trigger {trigger_id} disappeared")
        return row
