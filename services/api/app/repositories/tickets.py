from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_TICKET_SELECT = """
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
           t.client_ticket_id,
           t.terminal_at,
           t.created_at,
           t.updated_at,
           h.current_seq AS version
    FROM tickets AS t
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'ticket'
     AND h.aggregate_id = t.id::text
"""


def insert_ticket(connection: Connection[Any], *, row: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO tickets (
            id,
            category_id,
            category_version,
            category_snapshot,
            reporter_id,
            subject_id,
            state,
            priority,
            owner_id,
            resolution,
            client_ticket_id,
            terminal_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["category_id"],
            row["category_version"],
            Jsonb(row["category_snapshot"]),
            row["reporter_id"],
            row.get("subject_id"),
            row["state"],
            row["priority"],
            row.get("owner_id"),
            row.get("resolution"),
            row.get("client_ticket_id"),
            row.get("terminal_at"),
        ),
    )


def get_ticket(connection: Connection[Any], ticket_id: UUID) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TICKET_SELECT + " WHERE t.id = %s",
            (ticket_id,),
        ).fetchone()


def get_ticket_for_update(
    connection: Connection[Any],
    ticket_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TICKET_SELECT + " WHERE t.id = %s FOR UPDATE OF t",
            (ticket_id,),
        ).fetchone()


def get_ticket_by_category_client_ticket_id(
    connection: Connection[Any],
    *,
    category_id: UUID,
    client_ticket_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TICKET_SELECT
            + " WHERE t.category_id = %s AND t.client_ticket_id = %s",
            (category_id, client_ticket_id),
        ).fetchone()


def update_ticket(
    connection: Connection[Any],
    *,
    ticket_id: UUID,
    patch_row: dict[str, Any],
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE tickets
            SET state = %s,
                priority = %s,
                owner_id = %s,
                resolution = %s,
                terminal_at = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING updated_at
            """,
            (
                patch_row["state"],
                patch_row["priority"],
                patch_row.get("owner_id"),
                patch_row.get("resolution"),
                patch_row.get("terminal_at"),
                ticket_id,
            ),
        ).fetchone()


def insert_ticket_transition(connection: Connection[Any], *, row: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO ticket_transitions (
            id,
            ticket_id,
            aggregate_seq,
            action,
            from_state,
            to_state,
            actor_kind,
            actor_id,
            originating_actor_kind,
            originating_actor_id,
            from_owner_id,
            to_owner_id,
            from_priority,
            to_priority,
            reason,
            resolution
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            row["id"],
            row["ticket_id"],
            row["aggregate_seq"],
            row["action"],
            row["from_state"],
            row["to_state"],
            row["actor_kind"],
            row["actor_id"],
            row.get("originating_actor_kind"),
            row.get("originating_actor_id"),
            row.get("from_owner_id"),
            row.get("to_owner_id"),
            row.get("from_priority"),
            row.get("to_priority"),
            row.get("reason"),
            row.get("resolution"),
        ),
    )


def list_ticket_transitions(
    connection: Connection[Any],
    *,
    ticket_id: UUID,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id,
                   ticket_id,
                   aggregate_seq,
                   action,
                   from_state,
                   to_state,
                   actor_kind,
                   actor_id,
                   originating_actor_kind,
                   originating_actor_id,
                   from_owner_id,
                   to_owner_id,
                   from_priority,
                   to_priority,
                   reason,
                   resolution,
                   recorded_at
            FROM ticket_transitions
            WHERE ticket_id = %s
            ORDER BY aggregate_seq ASC
            """,
            (ticket_id,),
        ).fetchall()
