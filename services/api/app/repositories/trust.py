from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


_TRUST_PROFILE_SELECT = """
    SELECT t.member_id,
           t.score,
           t.tier,
           t.signals,
           t.policy_version_id,
           t.config_version,
           h.current_seq AS version
    FROM trust_profiles AS t
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'trust_profile'
     AND h.aggregate_id = t.member_id::text
"""


class TrustRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def fetch_trust_profile_by_member_id(
        self,
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_trust_profile_by_member_id_on(connection, member_id)

    def _fetch_trust_profile_by_member_id_on(
        self,
        connection: Connection[Any],
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _TRUST_PROFILE_SELECT + " WHERE t.member_id = %s",
                (member_id,),
            ).fetchone()

    def update_trust_profile(
        self,
        *,
        member_id: UUID,
        row: dict[str, Any],
    ) -> None:
        with self.db.connection() as connection:
            self._update_trust_profile_on(connection, member_id=member_id, row=row)

    def _update_trust_profile_on(
        self,
        connection: Connection[Any],
        *,
        member_id: UUID,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            UPDATE trust_profiles
            SET score = %s,
                tier = %s,
                signals = %s,
                policy_version_id = %s,
                config_version = %s,
                computed_at = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE member_id = %s
            """,
            (
                row["score"],
                row["tier"],
                Jsonb(row["signals"]),
                row["policy_version_id"],
                row["config_version"],
                row["computed_at"],
                member_id,
            ),
        )

    def upsert_trust_profile_for_recompute(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._upsert_trust_profile_for_recompute_on(connection, row=row)

    def _upsert_trust_profile_for_recompute_on(
        self,
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
                policy_version_id,
                config_version,
                computed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (member_id) DO UPDATE
            SET score = EXCLUDED.score,
                tier = EXCLUDED.tier,
                signals = EXCLUDED.signals,
                policy_version_id = EXCLUDED.policy_version_id,
                config_version = EXCLUDED.config_version,
                computed_at = EXCLUDED.computed_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                row["member_id"],
                row["score"],
                row["tier"],
                Jsonb(row["signals"]),
                row["policy_version_id"],
                row["config_version"],
                row["computed_at"],
            ),
        )

    def insert_trust_signal(self, *, row: dict[str, Any]) -> dict[str, Any]:
        with self.db.connection() as connection:
            return self._insert_trust_signal_on(connection, row=row)

    def _insert_trust_signal_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        with connection.cursor(row_factory=dict_row) as cursor:
            inserted = cursor.execute(
                """
                INSERT INTO trust_signals (
                    id,
                    member_id,
                    signal_type,
                    scope_kind,
                    scope_id,
                    scope,
                    value,
                    source_actor_kind,
                    source_actor_id,
                    observed_at,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, member_id, signal_type, scope_kind, scope_id, scope,
                          value, source_actor_kind, source_actor_id, observed_at,
                          expires_at, created_at
                """,
                (
                    row["id"],
                    row["member_id"],
                    row["signal_type"],
                    row["scope_kind"],
                    row["scope_id"],
                    Jsonb(row["scope"]),
                    Jsonb(row["value"]),
                    row["source_actor_kind"],
                    row["source_actor_id"],
                    row["observed_at"],
                    row["expires_at"],
                ),
            ).fetchone()
        if inserted is None:
            raise RuntimeError("failed to insert trust signal")
        return inserted

    def list_active_signals_for_member(
        self,
        *,
        member_id: UUID,
        as_of: datetime,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_active_signals_for_member_on(
                connection,
                member_id=member_id,
                as_of=as_of,
            )

    def _list_active_signals_for_member_on(
        self,
        connection: Connection[Any],
        *,
        member_id: UUID,
        as_of: datetime,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return list(
                cursor.execute(
                    """
                    SELECT id, member_id, signal_type, scope_kind, scope_id, scope,
                           value, source_actor_kind, source_actor_id, observed_at,
                           expires_at, created_at
                    FROM trust_signals
                    WHERE member_id = %s
                      AND (expires_at IS NULL OR expires_at > %s)
                    ORDER BY observed_at ASC, created_at ASC, id ASC
                    """,
                    (member_id, as_of),
                ).fetchall()
            )

    def get_trust_profile_for_update(
        self,
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_trust_profile_for_update_on(connection, member_id)

    def _get_trust_profile_for_update_on(
        self,
        connection: Connection[Any],
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _TRUST_PROFILE_SELECT
                + """
                  WHERE t.member_id = %s
                  FOR UPDATE OF t, h
                """,
                (member_id,),
            ).fetchone()


__all__ = ["TrustRepository"]
