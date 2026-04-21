from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_TRUST_PROFILE_SELECT = """
    SELECT t.member_id,
           t.score,
           t.tier,
           t.signals,
           t.policy_version_id,
           h.current_seq AS version
    FROM trust_profiles AS t
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'trust_profile'
     AND h.aggregate_id = t.member_id::text
"""


def fetch_trust_profile_by_member_id(
    connection: Connection[Any],
    member_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _TRUST_PROFILE_SELECT + " WHERE t.member_id = %s",
            (member_id,),
        ).fetchone()


def _insert_trust_profile(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO trust_profiles (
            member_id,
            score,
            tier,
            signals,
            policy_version_id
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            row["member_id"],
            row["score"],
            row["tier"],
            Jsonb(row["signals"]),
            row["policy_version_id"],
        ),
    )


__all__ = [
    "_insert_trust_profile",
    "fetch_trust_profile_by_member_id",
]
