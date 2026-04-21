from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


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


def insert_application(connection: Connection[Any], *, row: dict[str, Any]) -> dict[str, Any]:
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


def get_application(
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


def update_application(
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


def insert_review_row(connection: Connection[Any], *, row: dict[str, Any]) -> dict[str, Any]:
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
