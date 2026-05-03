from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


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


class TicketsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_ticket(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_ticket_on(connection, row=row)

    def _insert_ticket_on(self, connection: Connection[Any], *, row: dict[str, Any]) -> None:
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

    def get_ticket(self, ticket_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_ticket_on(connection, ticket_id)

    def _get_ticket_on(
        self,
        connection: Connection[Any],
        ticket_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _TICKET_SELECT + " WHERE t.id = %s",
                (ticket_id,),
            ).fetchone()

    def get_ticket_for_update(self, ticket_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_ticket_for_update_on(connection, ticket_id)

    def _get_ticket_for_update_on(
        self,
        connection: Connection[Any],
        ticket_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _TICKET_SELECT + " WHERE t.id = %s FOR UPDATE OF t",
                (ticket_id,),
            ).fetchone()

    def get_ticket_by_category_client_ticket_id(
        self,
        *,
        category_id: UUID,
        client_ticket_id: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_ticket_by_category_client_ticket_id_on(
                connection,
                category_id=category_id,
                client_ticket_id=client_ticket_id,
            )

    def _get_ticket_by_category_client_ticket_id_on(
        self,
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
        self,
        *,
        ticket_id: UUID,
        patch_row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._update_ticket_on(
                connection,
                ticket_id=ticket_id,
                patch_row=patch_row,
            )

    def _update_ticket_on(
        self,
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

    def insert_ticket_transition(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_ticket_transition_on(connection, row=row)

    def _insert_ticket_transition_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
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

    def list_open_tickets_for_owner_ids(
        self,
        *,
        owner_ids: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_open_tickets_for_owner_ids_on(
                connection,
                owner_ids=owner_ids,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )

    def _list_open_tickets_for_owner_ids_on(
        self,
        connection: Connection[Any],
        *,
        owner_ids: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not owner_ids:
            return []

        predicates = [
            "t.terminal_at IS NULL",
            "t.owner_id = ANY(%s)",
        ]
        params: list[Any] = [owner_ids]
        if scope_kind is not None:
            predicates.append("t.category_snapshot #>> '{routing_scope,scope_kind}' = %s")
            params.append(scope_kind)
        if scope_id is not None:
            predicates.append("t.category_snapshot #>> '{routing_scope,scope_id}' = %s")
            params.append(scope_id)

        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                f"""
                SELECT t.id,
                       t.owner_id,
                       t.state,
                       h.current_seq AS version
                FROM tickets AS t
                JOIN aggregate_heads AS h
                  ON h.aggregate_type = 'ticket'
                 AND h.aggregate_id = t.id::text
                WHERE {' AND '.join(predicates)}
                ORDER BY t.created_at ASC, t.id ASC
                """,
                params,
            ).fetchall()
