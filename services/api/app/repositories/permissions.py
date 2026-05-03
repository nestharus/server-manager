from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


def db_value_to_bit_str(value: Decimal | int | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ValueError(f"expected integer numeric bit mask, got {value!r}")
        return format(value, "f").split(".", 1)[0]
    return str(value)


def _normalize_permission_intent_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["permission_bits"] = db_value_to_bit_str(row.get("permission_bits"))
    normalized["allow_bits"] = db_value_to_bit_str(row.get("allow_bits"))
    normalized["deny_bits"] = db_value_to_bit_str(row.get("deny_bits"))
    if normalized["kind"] == "guild_role":
        normalized.pop("channel_id", None)
        normalized.pop("allow_bits", None)
        normalized.pop("deny_bits", None)
    if normalized["kind"] == "channel_role":
        normalized.pop("permission_bits", None)
    return normalized


def _normalize_permission_drift_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for field in (
        "actual_bits",
        "actual_allow_bits",
        "actual_deny_bits",
        "intended_bits",
        "intended_allow_bits",
        "intended_deny_bits",
    ):
        normalized[field] = db_value_to_bit_str(row.get(field))
    return normalized



class PermissionsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_permission_intent(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            return self._insert_permission_intent_on(connection, row=row)

    def fetch_permission_intent(self, intent_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_permission_intent_on(connection, intent_id)

    def list_permission_intents(
        self,
        *,
        scope_kind: str,
        scope_id: str | None,
        role_id: str | None = None,
        channel_id: str | None = None,
        kind: str | None = None,
        temporary: bool | None = None,
        include_expired: bool = False,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_permission_intents_on(
                connection,
                scope_kind=scope_kind,
                scope_id=scope_id,
                role_id=role_id,
                channel_id=channel_id,
                kind=kind,
                temporary=temporary,
                include_expired=include_expired,
            )

    def update_permission_intent_row(
        self,
        *,
        intent_id: UUID,
        row: dict[str, Any],
    ) -> int:
        with self.db.connection() as connection:
            return self._update_permission_intent_row_on(
                connection, intent_id=intent_id, row=row
            )

    def select_expirable_intents(
        self,
        *,
        now: datetime,
        batch_size: int,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._select_expirable_intents_on(
                connection, now=now, batch_size=batch_size
            )

    def mark_intent_expired_row(
        self,
        *,
        intent_id: UUID,
        expired_at: datetime,
    ) -> int:
        with self.db.connection() as connection:
            return self._mark_intent_expired_row_on(
                connection, intent_id=intent_id, expired_at=expired_at
            )

    def fetch_permission_drift(self, drift_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_permission_drift_on(connection, drift_id)

    def list_permission_drift(
        self,
        *,
        status: list[str] | None = None,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        role_id: str | None = None,
        reconciliation_run_id: UUID | None = None,
        has_intent: bool | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_permission_drift_on(
                connection,
                status=status,
                scope_kind=scope_kind,
                scope_id=scope_id,
                role_id=role_id,
                reconciliation_run_id=reconciliation_run_id,
                has_intent=has_intent,
            )

    def insert_permission_drift(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            return self._insert_permission_drift_on(connection, row=row)

    def insert_permission_drift_batch(
        self,
        *,
        rows: Sequence[dict[str, Any]],
    ) -> list[UUID]:
        with self.db.connection() as connection:
            return self._insert_permission_drift_batch_on(connection, rows=rows)

    def update_permission_drift_resolution(
        self,
        *,
        drift_id: UUID,
        status: str,
        resolved_by_kind: str | None,
        resolved_by_id: str | None,
        resolved_at: datetime | None,
        resolution_reason: str | None,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_permission_drift_resolution_on(
                connection,
                drift_id=drift_id,
                status=status,
                resolved_by_kind=resolved_by_kind,
                resolved_by_id=resolved_by_id,
                resolved_at=resolved_at,
                resolution_reason=resolution_reason,
            )

    def insert_reconciliation_run(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            return self._insert_reconciliation_run_on(connection, row=row)

    def fetch_reconciliation_run(self, run_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_reconciliation_run_on(connection, run_id)

    def update_reconciliation_run_status(
        self,
        *,
        run_id: UUID,
        status: str,
        snapshot_submitted_at: datetime | None = None,
        reconciled_at: datetime | None = None,
        failed_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_reconciliation_run_status_on(
                connection,
                run_id=run_id,
                status=status,
                snapshot_submitted_at=snapshot_submitted_at,
                reconciled_at=reconciled_at,
                failed_at=failed_at,
                failure_reason=failure_reason,
            )

    def list_drift_ids_by_run(self, run_id: UUID) -> list[UUID]:
        with self.db.connection() as connection:
            return self._list_drift_ids_by_run_on(connection, run_id)

    def _insert_permission_intent_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO permission_intents (
                id,
                kind,
                scope_kind,
                scope_id,
                role_id,
                channel_id,
                permission_bits,
                allow_bits,
                deny_bits,
                reason,
                temporary,
                expires_at,
                expired_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["kind"],
                row["scope_kind"],
                row["scope_id"],
                row["role_id"],
                row.get("channel_id"),
                row.get("permission_bits"),
                row.get("allow_bits"),
                row.get("deny_bits"),
                row.get("reason"),
                row["temporary"],
                row.get("expires_at"),
                row.get("expired_at"),
            ),
        )

    def _fetch_permission_intent_on(
        self,
        connection: Connection[Any],
        intent_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                       permission_bits, allow_bits, deny_bits, reason,
                       temporary, expires_at, expired_at
                FROM permission_intents
                WHERE id = %s
                """,
                (intent_id,),
            ).fetchone()
        if row is None:
            return None
        return _normalize_permission_intent_row(row)

    def _list_permission_intents_on(
        self,
        connection: Connection[Any],
        *,
        scope_kind: str,
        scope_id: str | None,
        role_id: str | None = None,
        channel_id: str | None = None,
        kind: str | None = None,
        temporary: bool | None = None,
        include_expired: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["scope_kind = %s"]
        params: list[Any] = [scope_kind]
        if scope_id is None:
            clauses.append("scope_id IS NULL")
        else:
            clauses.append("scope_id = %s")
            params.append(scope_id)
        if role_id is not None:
            clauses.append("role_id = %s")
            params.append(role_id)
        if channel_id is not None:
            clauses.append("channel_id = %s")
            params.append(channel_id)
        if kind is not None:
            clauses.append("kind = %s")
            params.append(kind)
        if temporary is not None:
            clauses.append("temporary = %s")
            params.append(temporary)
        if not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)")
        where = " AND ".join(clauses)
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                       permission_bits, allow_bits, deny_bits, reason,
                       temporary, expires_at, expired_at
                FROM permission_intents
                WHERE {where}
                ORDER BY role_id, channel_id NULLS FIRST, id
                """,
                params,
            ).fetchall()
        return [_normalize_permission_intent_row(row) for row in rows]

    def _update_permission_intent_row_on(
        self,
        connection: Connection[Any],
        *,
        intent_id: UUID,
        row: dict[str, Any],
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE permission_intents
            SET reason = %s,
                temporary = %s,
                expires_at = %s,
                permission_bits = %s,
                allow_bits = %s,
                deny_bits = %s
            WHERE id = %s
            """,
            (
                row.get("reason"),
                row["temporary"],
                row.get("expires_at"),
                row.get("permission_bits"),
                row.get("allow_bits"),
                row.get("deny_bits"),
                intent_id,
            ),
        )
        return cursor.rowcount

    def _select_expirable_intents_on(
        self,
        connection: Connection[Any],
        *,
        now: datetime,
        batch_size: int,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                       permission_bits, allow_bits, deny_bits, reason,
                       temporary, expires_at, expired_at
                FROM permission_intents
                WHERE temporary = TRUE
                  AND expires_at <= %s
                  AND expired_at IS NULL
                ORDER BY expires_at ASC, id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (now, batch_size),
            ).fetchall()
        return [_normalize_permission_intent_row(row) for row in rows]

    def _mark_intent_expired_row_on(
        self,
        connection: Connection[Any],
        *,
        intent_id: UUID,
        expired_at: datetime,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE permission_intents
            SET expired_at = %s
            WHERE id = %s
              AND expired_at IS NULL
            """,
            (expired_at, intent_id),
        )
        return cursor.rowcount

    def _fetch_permission_drift_on(
        self,
        connection: Connection[Any],
        drift_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT id, permission_intent_id, intent_version,
                       scope_kind, scope_id, role_id, channel_id, kind,
                       reconciliation_run_id,
                       actual_bits, actual_allow_bits, actual_deny_bits,
                       intended_bits, intended_allow_bits, intended_deny_bits,
                       status, detected_at,
                       resolved_by_kind, resolved_by_id, resolved_at,
                       resolution_reason
                FROM permission_drift
                WHERE id = %s
                """,
                (drift_id,),
            ).fetchone()
        if row is None:
            return None
        return _normalize_permission_drift_row(row)

    def _list_permission_drift_on(
        self,
        connection: Connection[Any],
        *,
        status: list[str] | None = None,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        role_id: str | None = None,
        reconciliation_run_id: UUID | None = None,
        has_intent: bool | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            placeholders = ", ".join(["%s"] * len(status))
            clauses.append(f"status IN ({placeholders})")
            params.extend(status)
        if scope_kind is not None:
            clauses.append("scope_kind = %s")
            params.append(scope_kind)
        if scope_id is not None:
            clauses.append("scope_id = %s")
            params.append(scope_id)
        if role_id is not None:
            clauses.append("role_id = %s")
            params.append(role_id)
        if reconciliation_run_id is not None:
            clauses.append("reconciliation_run_id = %s")
            params.append(reconciliation_run_id)
        if has_intent is True:
            clauses.append("permission_intent_id IS NOT NULL")
        elif has_intent is False:
            clauses.append("permission_intent_id IS NULL")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT id, permission_intent_id, intent_version,
                       scope_kind, scope_id, role_id, channel_id, kind,
                       reconciliation_run_id,
                       actual_bits, actual_allow_bits, actual_deny_bits,
                       intended_bits, intended_allow_bits, intended_deny_bits,
                       status, detected_at,
                       resolved_by_kind, resolved_by_id, resolved_at,
                       resolution_reason
                FROM permission_drift
                {where}
                ORDER BY detected_at DESC, id
                """,
                params,
            ).fetchall()
        return [_normalize_permission_drift_row(row) for row in rows]

    def _insert_permission_drift_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO permission_drift (
                id,
                permission_intent_id,
                intent_version,
                scope_kind,
                scope_id,
                role_id,
                channel_id,
                kind,
                reconciliation_run_id,
                actual_bits,
                actual_allow_bits,
                actual_deny_bits,
                intended_bits,
                intended_allow_bits,
                intended_deny_bits,
                status,
                detected_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row.get("permission_intent_id"),
                row.get("intent_version"),
                row["scope_kind"],
                row.get("scope_id"),
                row["role_id"],
                row.get("channel_id"),
                row["kind"],
                row.get("reconciliation_run_id"),
                row.get("actual_bits"),
                row.get("actual_allow_bits"),
                row.get("actual_deny_bits"),
                row.get("intended_bits"),
                row.get("intended_allow_bits"),
                row.get("intended_deny_bits"),
                row["status"],
                row["detected_at"],
            ),
        )

    def _insert_permission_drift_batch_on(
        self,
        connection: Connection[Any],
        *,
        rows: Sequence[dict[str, Any]],
    ) -> list[UUID]:
        inserted: list[UUID] = []
        for row in rows:
            result = connection.execute(
                """
                INSERT INTO permission_drift (
                    id, permission_intent_id, intent_version,
                    scope_kind, scope_id, role_id, channel_id, kind,
                    reconciliation_run_id,
                    actual_bits, actual_allow_bits, actual_deny_bits,
                    intended_bits, intended_allow_bits, intended_deny_bits,
                    status, detected_at
                ) VALUES (
                    %(id)s, %(permission_intent_id)s, %(intent_version)s,
                    %(scope_kind)s, %(scope_id)s, %(role_id)s, %(channel_id)s,
                    %(kind)s, %(reconciliation_run_id)s,
                    %(actual_bits)s, %(actual_allow_bits)s, %(actual_deny_bits)s,
                    %(intended_bits)s, %(intended_allow_bits)s, %(intended_deny_bits)s,
                    %(status)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                row,
            ).fetchone()
            if result is not None:
                inserted.append(result[0])
        return inserted

    def _update_permission_drift_resolution_on(
        self,
        connection: Connection[Any],
        *,
        drift_id: UUID,
        status: str,
        resolved_by_kind: str | None,
        resolved_by_id: str | None,
        resolved_at: datetime | None,
        resolution_reason: str | None,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE permission_drift
               SET status = %s,
                   resolved_by_kind = %s,
                   resolved_by_id = %s,
                   resolved_at = %s,
                   resolution_reason = %s
             WHERE id = %s
            """,
            (
                status,
                resolved_by_kind,
                resolved_by_id,
                resolved_at,
                resolution_reason,
                drift_id,
            ),
        )
        return cursor.rowcount

    def _insert_reconciliation_run_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO permission_reconciliation_runs (
                id, scope_kind, scope_id,
                requested_by_kind, requested_by_id,
                requested_at, status
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'requested')
            """,
            (
                row["id"],
                row["scope_kind"],
                row["scope_id"],
                row["requested_by_kind"],
                row["requested_by_id"],
            ),
        )

    def _fetch_reconciliation_run_on(
        self,
        connection: Connection[Any],
        run_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, scope_kind, scope_id,
                       requested_by_kind, requested_by_id, requested_at,
                       snapshot_submitted_at, reconciled_at,
                       failed_at, failure_reason, status
                FROM permission_reconciliation_runs
                WHERE id = %s
                """,
                (run_id,),
            ).fetchone()

    def _update_reconciliation_run_status_on(
        self,
        connection: Connection[Any],
        *,
        run_id: UUID,
        status: str,
        snapshot_submitted_at: datetime | None = None,
        reconciled_at: datetime | None = None,
        failed_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE permission_reconciliation_runs
               SET status = %s,
                   snapshot_submitted_at = COALESCE(%s, snapshot_submitted_at),
                   reconciled_at = COALESCE(%s, reconciled_at),
                   failed_at = COALESCE(%s, failed_at),
                   failure_reason = COALESCE(%s, failure_reason)
             WHERE id = %s
            """,
            (
                status,
                snapshot_submitted_at,
                reconciled_at,
                failed_at,
                failure_reason,
                run_id,
            ),
        )
        return cursor.rowcount

    def _list_drift_ids_by_run_on(
        self,
        connection: Connection[Any],
        run_id: UUID,
    ) -> list[UUID]:
        rows = connection.execute(
            """
            SELECT id FROM permission_drift
             WHERE reconciliation_run_id = %s
             ORDER BY detected_at, id
            """,
            (run_id,),
        ).fetchall()
        return [row[0] for row in rows]
