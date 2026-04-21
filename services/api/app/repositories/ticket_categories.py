from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_TICKET_CATEGORY_SELECT = """
    SELECT c.id,
           c.name,
           c.routing_scope,
           c.privacy_level,
           c.state_machine,
           c.sla_rules,
           c.created_at,
           c.updated_at,
           h.current_seq AS version
    FROM ticket_categories AS c
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'ticket_category'
     AND h.aggregate_id = c.id::text
"""


def insert_ticket_category(connection: Connection[Any], *, row: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO ticket_categories (
            id,
            name,
            routing_scope,
            privacy_level,
            state_machine,
            sla_rules
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["name"],
            Jsonb(row["routing_scope"]),
            row["privacy_level"],
            Jsonb(row["state_machine"]),
            Jsonb(row["sla_rules"]),
        ),
    )


def get_ticket_category(
    connection: Connection[Any],
    category_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TICKET_CATEGORY_SELECT + " WHERE c.id = %s",
            (category_id,),
        ).fetchone()


def get_ticket_category_for_update(
    connection: Connection[Any],
    category_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TICKET_CATEGORY_SELECT + " WHERE c.id = %s FOR UPDATE OF c",
            (category_id,),
        ).fetchone()


def update_ticket_category(
    connection: Connection[Any],
    *,
    category_id: UUID,
    patch_row: dict[str, Any],
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE ticket_categories
            SET name = %s,
                routing_scope = %s,
                privacy_level = %s,
                state_machine = %s,
                sla_rules = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING updated_at
            """,
            (
                patch_row["name"],
                Jsonb(patch_row["routing_scope"]),
                patch_row["privacy_level"],
                Jsonb(patch_row["state_machine"]),
                Jsonb(patch_row["sla_rules"]),
                category_id,
            ),
        ).fetchone()
