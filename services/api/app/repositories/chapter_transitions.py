from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


def insert_chapter_transition(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO chapter_transitions (
            id,
            chapter_id,
            aggregate_seq,
            from_state,
            to_state,
            actor_kind,
            actor_id,
            originating_actor_kind,
            originating_actor_id,
            reason
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["chapter_id"],
            row["aggregate_seq"],
            row["from_state"],
            row["to_state"],
            row["actor_kind"],
            row["actor_id"],
            row["originating_actor_kind"],
            row["originating_actor_id"],
            row["reason"],
        ),
    )


def list_chapter_transitions(
    connection: Connection[Any],
    chapter_id: str,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, chapter_id, aggregate_seq, from_state, to_state,
                   actor_kind, actor_id, originating_actor_kind,
                   originating_actor_id, reason, recorded_at
            FROM chapter_transitions
            WHERE chapter_id = %s
            ORDER BY aggregate_seq ASC
            """,
            (chapter_id,),
        ).fetchall()
