from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


class WebRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def list_admin_chapters(self) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
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
