from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


_APPLICATION_SELECT = """
    SELECT a.id,
           a.applicant_id,
           a.form_definition_id,
           a.form_version,
           a.form_snapshot,
           a.target_scope_kind,
           a.target_scope_id,
           a.responses,
           a.state,
           a.owner_id,
           a.interview_thread_id,
           a.decision_reason,
           a.client_application_id,
           a.submitted_at,
           a.queued_at,
           a.claimed_at,
           a.review_started_at,
           a.decided_at,
           a.withdrawn_at,
           a.created_at,
           a.updated_at,
           h.current_seq AS version
    FROM applications AS a
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'application'
     AND h.aggregate_id = a.id::text
"""


class ApplicationsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_application(self, *, row: dict[str, Any]) -> dict[str, Any]:
        with self.db.connection() as connection:
            return self._insert_application_on(connection, row=row)

    def _insert_application_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
            """
            INSERT INTO applications (
                id,
                applicant_id,
                form_definition_id,
                form_version,
                form_snapshot,
                target_scope_kind,
                target_scope_id,
                responses,
                state,
                owner_id,
                interview_thread_id,
                decision_reason,
                client_application_id,
                submitted_at,
                queued_at,
                claimed_at,
                review_started_at,
                decided_at,
                withdrawn_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
            """,
            (
                row["id"],
                row["applicant_id"],
                row["form_definition_id"],
                row["form_version"],
                Jsonb(row["form_snapshot"]),
                row["target_scope_kind"],
                row.get("target_scope_id"),
                Jsonb(row["responses"]),
                row["state"],
                row.get("owner_id"),
                row.get("interview_thread_id"),
                row.get("decision_reason"),
                row.get("client_application_id"),
                row["submitted_at"],
                row.get("queued_at"),
                row.get("claimed_at"),
                row.get("review_started_at"),
                row.get("decided_at"),
                row.get("withdrawn_at"),
            ),
            ).fetchone()

    def get_application(self, *, application_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_application_on(connection, application_id=application_id)

    def _get_application_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_SELECT + " WHERE a.id = %s",
                (application_id,),
            ).fetchone()

    def get_application_for_update(
        self,
        *,
        application_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_application_for_update_on(
                connection,
                application_id=application_id,
            )

    def _get_application_for_update_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_SELECT + " WHERE a.id = %s FOR UPDATE OF a",
                (application_id,),
            ).fetchone()

    def get_application_by_client_application_id(
        self,
        *,
        applicant_id: UUID,
        client_application_id: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_application_by_client_application_id_on(
                connection,
                applicant_id=applicant_id,
                client_application_id=client_application_id,
            )

    def _get_application_by_client_application_id_on(
        self,
        connection: Connection[Any],
        *,
        applicant_id: UUID,
        client_application_id: str,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_SELECT
                + " WHERE a.applicant_id = %s AND a.client_application_id = %s",
                (applicant_id, client_application_id),
            ).fetchone()

    def list_applications(
        self,
        *,
        states: frozenset[str] | None,
        scope_kind: str | None,
        scope_id: str | None,
        owner_id: UUID | None,
        limit: int,
        after_id: UUID | None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_applications_on(
                connection,
                states=states,
                scope_kind=scope_kind,
                scope_id=scope_id,
                owner_id=owner_id,
                limit=limit,
                after_id=after_id,
            )

    def _list_applications_on(
        self,
        connection: Connection[Any],
        *,
        states: frozenset[str] | None,
        scope_kind: str | None,
        scope_id: str | None,
        owner_id: UUID | None,
        limit: int,
        after_id: UUID | None,
    ) -> list[dict[str, Any]]:
        predicates: list[str] = []
        params: list[Any] = []
        if states is not None:
            predicates.append("a.state = ANY(%s)")
            params.append(sorted(states))
        if scope_kind is not None:
            predicates.append("a.target_scope_kind = %s")
            params.append(scope_kind)
        if scope_id is not None:
            predicates.append("a.target_scope_id = %s")
            params.append(scope_id)
        if owner_id is not None:
            predicates.append("a.owner_id = %s")
            params.append(owner_id)
        if after_id is not None:
            predicates.append(
                """
                (
                    a.submitted_at < (
                        SELECT cursor_app.submitted_at
                        FROM applications AS cursor_app
                        WHERE cursor_app.id = %s
                    )
                    OR (
                        a.submitted_at = (
                            SELECT cursor_app.submitted_at
                            FROM applications AS cursor_app
                            WHERE cursor_app.id = %s
                        )
                        AND a.id > %s
                    )
                )
                """
            )
            params.extend([after_id, after_id, after_id])

        where_clause = "" if not predicates else f" WHERE {' AND '.join(predicates)}"
        params.append(limit + 1)
        with connection.cursor(row_factory=dict_row) as cursor:
            return list(
                cursor.execute(
                    _APPLICATION_SELECT
                    + where_clause
                    + " ORDER BY a.submitted_at DESC, a.id ASC LIMIT %s",
                    params,
                ).fetchall()
            )

    def update_application(
        self,
        *,
        application_id: UUID,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._update_application_on(
                connection,
                application_id=application_id,
                row=row,
            )

    def _update_application_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
            """
            UPDATE applications
            SET state = %s,
                owner_id = %s,
                interview_thread_id = %s,
                decision_reason = %s,
                queued_at = %s,
                claimed_at = %s,
                review_started_at = %s,
                decided_at = %s,
                withdrawn_at = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                row["state"],
                row.get("owner_id"),
                row.get("interview_thread_id"),
                row.get("decision_reason"),
                row.get("queued_at"),
                row.get("claimed_at"),
                row.get("review_started_at"),
                row.get("decided_at"),
                row.get("withdrawn_at"),
                application_id,
            ),
            ).fetchone()

    def insert_review_row(self, *, row: dict[str, Any]) -> dict[str, Any]:
        with self.db.connection() as connection:
            return self._insert_review_row_on(connection, row=row)

    def _insert_review_row_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
            """
            INSERT INTO application_reviews (
                id,
                application_id,
                aggregate_seq,
                reviewer_id,
                actor_kind,
                actor_id,
                action,
                from_state,
                to_state,
                notes,
                decision_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                row["id"],
                row["application_id"],
                row["aggregate_seq"],
                row.get("reviewer_id"),
                row["actor_kind"],
                row["actor_id"],
                row["action"],
                row["from_state"],
                row["to_state"],
                row.get("notes"),
                row.get("decision_reason"),
            ),
            ).fetchone()

    def list_application_state_changes(
        self,
        *,
        application_id: UUID,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_application_state_changes_on(
                connection,
                application_id=application_id,
            )

    def _list_application_state_changes_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
            """
            SELECT sc.aggregate_seq,
                   sc.change_type,
                   sc.payload_json,
                   sc.diff_json,
                   sc.recorded_at,
                   aa.actor_kind,
                   aa.actor_id
            FROM activity_state_changes AS sc
            JOIN activity_actions AS aa
              ON aa.id = sc.action_id
            WHERE sc.aggregate_type = 'application'
              AND sc.aggregate_id = %s
            ORDER BY sc.aggregate_seq ASC
            """,
            (str(application_id),),
        ).fetchall()
        return list(rows)

    def list_open_applications_for_owner_ids(
        self,
        *,
        owner_ids: list[UUID],
        states: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not owner_ids:
            return []
        with self.db.connection() as connection:
            return self._list_open_applications_for_owner_ids_on(
                connection,
                owner_ids=owner_ids,
                states=states,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )

    def _list_open_applications_for_owner_ids_on(
        self,
        connection: Connection[Any],
        *,
        owner_ids: list[UUID],
        states: list[str],
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not owner_ids:
            return []

        predicates = [
            "a.owner_id = ANY(%s)",
            "a.state = ANY(%s)",
        ]
        params: list[Any] = [owner_ids, states]
        if scope_kind is not None:
            predicates.append("a.target_scope_kind = %s")
            params.append(scope_kind)
        if scope_id is not None:
            predicates.append("a.target_scope_id = %s")
            params.append(scope_id)

        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
            f"""
            SELECT a.id,
                   a.owner_id,
                   a.state,
                   h.current_seq AS version
            FROM applications AS a
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'application'
             AND h.aggregate_id = a.id::text
            WHERE {' AND '.join(predicates)}
            ORDER BY a.created_at ASC, a.id ASC
            """,
            params,
            ).fetchall()
