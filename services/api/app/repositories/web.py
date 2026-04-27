from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


def list_admin_chapters(connection: Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """
            SELECT c.id, c.name, c.state, c.created_at, h.current_seq AS version
            FROM chapters AS c
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'chapter'
             AND h.aggregate_id = c.id
            ORDER BY c.created_at DESC, c.name ASC
            LIMIT 200
            """
        ).fetchall()
    return list(rows)
