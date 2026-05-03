from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


class AuthorityRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_grant(self, *, grant_row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_grant_on(connection, grant_row=grant_row)

    def _insert_grant_on(
        self,
        connection: Connection[Any],
        *,
        grant_row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO authority_grants (
                id,
                grantee_id,
                scope_kind,
                scope_id,
                permissions,
                expires_at,
                revoked_at,
                revoked_by,
                revocation_reason,
                predecessor_grant_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                grant_row["id"],
                grant_row["grantee_id"],
                grant_row["scope_kind"],
                grant_row["scope_id"],
                Jsonb(sorted(grant_row["permissions"])),
                grant_row["expires_at"],
                grant_row["revoked_at"],
                grant_row["revoked_by"],
                grant_row["revocation_reason"],
                grant_row["predecessor_grant_id"],
            ),
        )

    def fetch_grant(self, *, grant_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_grant_on(connection, grant_id=grant_id)

    def _fetch_grant_on(
        self,
        connection: Connection[Any],
        *,
        grant_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT g.id, g.grantee_id, g.scope_kind, g.scope_id, g.permissions,
                       g.expires_at, g.revoked_at, g.revoked_by, g.revocation_reason,
                       g.predecessor_grant_id, g.created_at, h.current_seq
                FROM authority_grants AS g
                JOIN aggregate_heads AS h
                  ON h.aggregate_type = 'authority_grant'
                 AND h.aggregate_id = g.id::text
                WHERE g.id = %s
                """,
                (grant_id,),
            ).fetchone()

    def list_grants(
        self,
        *,
        grantee_id: str,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        include_revoked: bool = False,
        limit: int | None = None,
        after_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_grants_on(
                connection,
                grantee_id=grantee_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                include_revoked=include_revoked,
                limit=limit,
                after_id=after_id,
            )

    def _list_grants_on(
        self,
        connection: Connection[Any],
        *,
        grantee_id: str,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        include_revoked: bool = False,
        limit: int | None = None,
        after_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        predicates = ["grantee_id = %s"]
        params: list[object] = [grantee_id]

        if scope_kind is not None:
            predicates.append("scope_kind = %s")
            params.append(scope_kind)
        if scope_id is not None:
            predicates.append("scope_id = %s")
            params.append(scope_id)
        if not include_revoked:
            predicates.append("revoked_at IS NULL")
        if after_id is not None:
            predicates.append(
                """
                (created_at, id) > (
                    SELECT created_at, id
                    FROM authority_grants
                    WHERE id = %s
                )
                """
            )
            params.append(after_id)

        query = f"""
            SELECT id, grantee_id, scope_kind, scope_id, permissions,
                   expires_at, revoked_at, revoked_by, revocation_reason,
                   predecessor_grant_id, created_at
            FROM authority_grants
            WHERE {' AND '.join(predicates)}
            ORDER BY created_at ASC, id ASC
        """
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(query, params).fetchall()

    def list_active_grants_for_grantee_ids(
        self,
        *,
        grantee_ids: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_active_grants_for_grantee_ids_on(
                connection,
                grantee_ids=grantee_ids,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )

    def _list_active_grants_for_grantee_ids_on(
        self,
        connection: Connection[Any],
        *,
        grantee_ids: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not grantee_ids:
            return []

        predicates = [
            "grantee_id = ANY(%s)",
            "revoked_at IS NULL",
            "(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
        ]
        params: list[object] = [grantee_ids]
        if scope_kind is not None:
            predicates.append("scope_kind = %s")
            params.append(scope_kind)
        if scope_id is not None:
            predicates.append("scope_id = %s")
            params.append(scope_id)

        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                f"""
                SELECT id, grantee_id, scope_kind, scope_id, permissions,
                       expires_at, revoked_at, revoked_by, revocation_reason,
                       predecessor_grant_id, created_at
                FROM authority_grants
                WHERE {' AND '.join(predicates)}
                ORDER BY created_at ASC, id ASC
                """,
                params,
            ).fetchall()

    def find_active_duplicate_grant_for_update(
        self,
        *,
        grantee_id: str,
        scope_kind: str,
        scope_id: str | None,
        permissions: frozenset[str],
        at: datetime,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._find_active_duplicate_grant_for_update_on(
                connection,
                grantee_id=grantee_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                permissions=permissions,
                at=at,
            )

    def _find_active_duplicate_grant_for_update_on(
        self,
        connection: Connection[Any],
        *,
        grantee_id: str,
        scope_kind: str,
        scope_id: str | None,
        permissions: frozenset[str],
        at: datetime,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, grantee_id, scope_kind, scope_id, permissions,
                       expires_at, revoked_at, revoked_by, revocation_reason,
                       predecessor_grant_id, created_at
                FROM authority_grants
                WHERE grantee_id = %s
                  AND scope_kind = %s
                  AND scope_id IS NOT DISTINCT FROM %s
                  AND permissions = %s::jsonb
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > %s)
                ORDER BY created_at ASC, id ASC
                FOR UPDATE
                """,
                (grantee_id, scope_kind, scope_id, Jsonb(sorted(permissions)), at),
            ).fetchone()

    def find_successor_grant(
        self,
        *,
        predecessor_grant_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._find_successor_grant_on(
                connection,
                predecessor_grant_id=predecessor_grant_id,
            )

    def _find_successor_grant_on(
        self,
        connection: Connection[Any],
        *,
        predecessor_grant_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, grantee_id, scope_kind, scope_id, permissions,
                       expires_at, revoked_at, revoked_by, revocation_reason,
                       predecessor_grant_id, created_at
                FROM authority_grants
                WHERE predecessor_grant_id = %s
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (predecessor_grant_id,),
            ).fetchone()

    def fetch_grants_by_ids(self, *, grant_ids: list[UUID]) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._fetch_grants_by_ids_on(connection, grant_ids=grant_ids)

    def _fetch_grants_by_ids_on(
        self,
        connection: Connection[Any],
        *,
        grant_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        if not grant_ids:
            return []
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, grantee_id, scope_kind, scope_id, permissions,
                       expires_at, revoked_at, revoked_by, revocation_reason,
                       predecessor_grant_id, created_at
                FROM authority_grants
                WHERE id = ANY(%s)
                ORDER BY created_at ASC, id ASC
                """,
                (grant_ids,),
            ).fetchall()

    def update_revoked_with_reason(
        self,
        *,
        grant_id: UUID,
        revoked_at: datetime,
        revoked_by: str,
        revocation_reason: str,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_revoked_with_reason_on(
                connection,
                grant_id=grant_id,
                revoked_at=revoked_at,
                revoked_by=revoked_by,
                revocation_reason=revocation_reason,
            )

    def _update_revoked_with_reason_on(
        self,
        connection: Connection[Any],
        *,
        grant_id: UUID,
        revoked_at: datetime,
        revoked_by: str,
        revocation_reason: str,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE authority_grants
            SET revoked_at = %s,
                revoked_by = %s,
                revocation_reason = %s
            WHERE id = %s AND revoked_at IS NULL
            """,
            (revoked_at, revoked_by, revocation_reason, grant_id),
        )
        return cursor.rowcount


__all__ = ["AuthorityRepository"]
