from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


_RULE_SELECT = """
    SELECT r.id,
           r.chapter_id,
           r.name,
           r.cadence_kind,
           r.cadence_params,
           r.evaluation_window_days,
           r.evidence_requirements,
           r.consequence_kind,
           r.consequence_params,
           r.active,
           r.archived_at,
           r.created_at,
           h.current_seq AS version
    FROM compliance_rules AS r
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'compliance_rule'
     AND h.aggregate_id = r.id::text
"""

_EVIDENCE_SELECT = """
    SELECT e.id,
           e.rule_id,
           e.member_id,
           e.chapter_id,
           e.attachment_ref,
           e.raw_text,
           e.extracted_fields,
           e.extracted_fields_corrected,
           e.extraction_status,
           e.extraction_confidence,
           e.extraction_error,
           e.submitted_by_member_id,
           e.submitted_at,
           e.corrected_by_member_id,
           e.corrected_at,
           e.correction_reason,
           h.current_seq AS version
    FROM evidence_submissions AS e
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'evidence_submission'
     AND h.aggregate_id = e.id::text
"""

_EVALUATION_SELECT = """
    SELECT e.id,
           e.rule_id,
           e.rule_version,
           e.chapter_id,
           e.member_id,
           e.period_start,
           e.period_end,
           e.result,
           e.consequence_applied,
           e.review_status,
           e.reviewer_id,
           e.review_reason,
           e.reviewed_at,
           e.evaluated_at,
           e.evidence_ids,
           h.current_seq AS version
    FROM compliance_evaluations AS e
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'compliance_evaluation'
     AND h.aggregate_id = e.id::text
"""


def _row_or_none(cursor_result: Any) -> dict[str, Any] | None:
    row = cursor_result.fetchone()
    return None if row is None else dict(row)


class ComplianceRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def get_rule(self, rule_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_rule_on(connection, rule_id)

    def _get_rule_on(
        self,
        connection: Connection[Any],
        rule_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _RULE_SELECT + " WHERE r.id = %s",
                (rule_id,),
            ).fetchone()

    def get_rule_for_update(self, rule_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_rule_for_update_on(connection, rule_id)

    def _get_rule_for_update_on(
        self,
        connection: Connection[Any],
        rule_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _RULE_SELECT + " WHERE r.id = %s FOR UPDATE OF r",
                (rule_id,),
            ).fetchone()

    def list_rules_by_chapter(
        self,
        *,
        chapter_id: str,
        active_only: bool,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_rules_by_chapter_on(
                connection,
                chapter_id=chapter_id,
                active_only=active_only,
            )

    def _list_rules_by_chapter_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
        active_only: bool,
    ) -> list[dict[str, Any]]:
        sql = _RULE_SELECT + " WHERE r.chapter_id = %s"
        if active_only:
            sql += " AND r.active = TRUE AND r.archived_at IS NULL"
        sql += " ORDER BY r.created_at ASC, r.id ASC"
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(sql, (chapter_id,)).fetchall()

    def list_active_rules(self) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_active_rules_on(connection)

    def _list_active_rules_on(
        self,
        connection: Connection[Any],
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _RULE_SELECT
                + " WHERE r.active = TRUE AND r.archived_at IS NULL"
                + " ORDER BY r.chapter_id ASC, r.created_at ASC, r.id ASC"
            ).fetchall()

    def insert_rule(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_rule_on(connection, row=row)

    def _insert_rule_on(self, connection: Connection[Any], *, row: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT INTO compliance_rules (
                id,
                chapter_id,
                name,
                cadence_kind,
                cadence_params,
                evaluation_window_days,
                evidence_requirements,
                consequence_kind,
                consequence_params,
                active,
                archived_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["chapter_id"],
                row["name"],
                row["cadence_kind"],
                Jsonb(row["cadence_params"]),
                row["evaluation_window_days"],
                Jsonb(row["evidence_requirements"]),
                row["consequence_kind"],
                Jsonb(row["consequence_params"]),
                row["active"],
                row["archived_at"],
            ),
        )

    def update_rule_row(self, *, rule_id: UUID, row: dict[str, Any]) -> int:
        with self.db.connection() as connection:
            return self._update_rule_row_on(connection, rule_id=rule_id, row=row)

    def _update_rule_row_on(
        self,
        connection: Connection[Any],
        *,
        rule_id: UUID,
        row: dict[str, Any],
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE compliance_rules
            SET name = %s,
                cadence_kind = %s,
                cadence_params = %s,
                evaluation_window_days = %s,
                evidence_requirements = %s,
                consequence_kind = %s,
                consequence_params = %s,
                active = %s,
                archived_at = %s
            WHERE id = %s
            """,
            (
                row["name"],
                row["cadence_kind"],
                Jsonb(row["cadence_params"]),
                row["evaluation_window_days"],
                Jsonb(row["evidence_requirements"]),
                row["consequence_kind"],
                Jsonb(row["consequence_params"]),
                row["active"],
                row["archived_at"],
                rule_id,
            ),
        )
        return cursor.rowcount

    def get_evidence(self, evidence_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_evidence_on(connection, evidence_id)

    def _get_evidence_on(
        self,
        connection: Connection[Any],
        evidence_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _EVIDENCE_SELECT + " WHERE e.id = %s",
                (evidence_id,),
            ).fetchone()

    def get_evidence_for_update(self, evidence_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_evidence_for_update_on(connection, evidence_id)

    def _get_evidence_for_update_on(
        self,
        connection: Connection[Any],
        evidence_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _EVIDENCE_SELECT + " WHERE e.id = %s FOR UPDATE OF e",
                (evidence_id,),
            ).fetchone()

    def insert_evidence(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_evidence_on(connection, row=row)

    def _insert_evidence_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO evidence_submissions (
                id,
                rule_id,
                member_id,
                chapter_id,
                attachment_ref,
                raw_text,
                extracted_fields,
                extracted_fields_corrected,
                extraction_status,
                extraction_confidence,
                extraction_error,
                submitted_by_member_id,
                corrected_by_member_id,
                corrected_at,
                correction_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["rule_id"],
                row["member_id"],
                row["chapter_id"],
                row["attachment_ref"],
                row.get("raw_text"),
                (
                    None
                    if row.get("extracted_fields") is None
                    else Jsonb(row["extracted_fields"])
                ),
                (
                    None
                    if row.get("extracted_fields_corrected") is None
                    else Jsonb(row["extracted_fields_corrected"])
                ),
                row["extraction_status"],
                row.get("extraction_confidence"),
                row.get("extraction_error"),
                row["submitted_by_member_id"],
                row.get("corrected_by_member_id"),
                row.get("corrected_at"),
                row.get("correction_reason"),
            ),
        )

    def update_evidence_after_extraction(
        self,
        *,
        evidence_id: UUID,
        raw_text: str | None,
        extracted_fields: dict[str, Any] | None,
        extraction_status: str,
        extraction_confidence: Decimal | None,
        extraction_error: str | None,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_evidence_after_extraction_on(
                connection,
                evidence_id=evidence_id,
                raw_text=raw_text,
                extracted_fields=extracted_fields,
                extraction_status=extraction_status,
                extraction_confidence=extraction_confidence,
                extraction_error=extraction_error,
            )

    def _update_evidence_after_extraction_on(
        self,
        connection: Connection[Any],
        *,
        evidence_id: UUID,
        raw_text: str | None,
        extracted_fields: dict[str, Any] | None,
        extraction_status: str,
        extraction_confidence: Decimal | None,
        extraction_error: str | None,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE evidence_submissions
            SET raw_text = %s,
                extracted_fields = %s,
                extraction_status = %s,
                extraction_confidence = %s,
                extraction_error = %s
            WHERE id = %s
            """,
            (
                raw_text,
                None if extracted_fields is None else Jsonb(extracted_fields),
                extraction_status,
                extraction_confidence,
                extraction_error,
                evidence_id,
            ),
        )
        return cursor.rowcount

    def update_evidence_correction(
        self,
        *,
        evidence_id: UUID,
        corrected_fields: dict[str, Any],
        corrected_by_member_id: str,
        corrected_at: datetime,
        correction_reason: str,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_evidence_correction_on(
                connection,
                evidence_id=evidence_id,
                corrected_fields=corrected_fields,
                corrected_by_member_id=corrected_by_member_id,
                corrected_at=corrected_at,
                correction_reason=correction_reason,
            )

    def _update_evidence_correction_on(
        self,
        connection: Connection[Any],
        *,
        evidence_id: UUID,
        corrected_fields: dict[str, Any],
        corrected_by_member_id: str,
        corrected_at: datetime,
        correction_reason: str,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE evidence_submissions
            SET extracted_fields_corrected = %s,
                extraction_status = 'corrected',
                corrected_by_member_id = %s,
                corrected_at = %s,
                correction_reason = %s
            WHERE id = %s
            """,
            (
                Jsonb(corrected_fields),
                corrected_by_member_id,
                corrected_at,
                correction_reason,
                evidence_id,
            ),
        )
        return cursor.rowcount

    def list_evidence_for_rule_period(
        self,
        *,
        rule_id: UUID,
        member_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_evidence_for_rule_period_on(
                connection,
                rule_id=rule_id,
                member_id=member_id,
                period_start=period_start,
                period_end=period_end,
            )

    def _list_evidence_for_rule_period_on(
        self,
        connection: Connection[Any],
        *,
        rule_id: UUID,
        member_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _EVIDENCE_SELECT
                + """
                  WHERE e.rule_id = %s
                    AND e.member_id = %s
                    AND DATE(e.submitted_at AT TIME ZONE 'UTC') BETWEEN %s AND %s
                  ORDER BY e.submitted_at ASC, e.id ASC
                """,
                (rule_id, member_id, period_start, period_end),
            ).fetchall()

    def get_evaluation(self, evaluation_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_evaluation_on(connection, evaluation_id)

    def _get_evaluation_on(
        self,
        connection: Connection[Any],
        evaluation_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _EVALUATION_SELECT + " WHERE e.id = %s",
                (evaluation_id,),
            ).fetchone()

    def get_evaluation_for_update(self, evaluation_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_evaluation_for_update_on(connection, evaluation_id)

    def _get_evaluation_for_update_on(
        self,
        connection: Connection[Any],
        evaluation_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _EVALUATION_SELECT + " WHERE e.id = %s FOR UPDATE OF e",
                (evaluation_id,),
            ).fetchone()

    def insert_evaluation_if_absent(
        self,
        *,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._insert_evaluation_if_absent_on(connection, row=row)

    def _insert_evaluation_if_absent_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                INSERT INTO compliance_evaluations (
                    id,
                    rule_id,
                    rule_version,
                    chapter_id,
                    member_id,
                    period_start,
                    period_end,
                    result,
                    consequence_applied,
                    review_status,
                    reviewer_id,
                    review_reason,
                    reviewed_at,
                    evidence_ids
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (member_id, rule_id, period_start, period_end)
                DO NOTHING
                RETURNING id, rule_id, rule_version, chapter_id, member_id, period_start,
                          period_end, result, consequence_applied, review_status,
                          reviewer_id, review_reason, reviewed_at, evaluated_at, evidence_ids
                """,
                (
                    row["id"],
                    row["rule_id"],
                    row["rule_version"],
                    row["chapter_id"],
                    row["member_id"],
                    row["period_start"],
                    row["period_end"],
                    row["result"],
                    row["consequence_applied"],
                    row["review_status"],
                    row.get("reviewer_id"),
                    row.get("review_reason"),
                    row.get("reviewed_at"),
                    Jsonb(row["evidence_ids"]),
                ),
            ).fetchone()

    def update_evaluation_review(
        self,
        *,
        evaluation_id: UUID,
        result: str,
        consequence_applied: str,
        review_status: str,
        reviewer_id: str,
        review_reason: str,
        reviewed_at: datetime,
    ) -> int:
        with self.db.connection() as connection:
            return self._update_evaluation_review_on(
                connection,
                evaluation_id=evaluation_id,
                result=result,
                consequence_applied=consequence_applied,
                review_status=review_status,
                reviewer_id=reviewer_id,
                review_reason=review_reason,
                reviewed_at=reviewed_at,
            )

    def _update_evaluation_review_on(
        self,
        connection: Connection[Any],
        *,
        evaluation_id: UUID,
        result: str,
        consequence_applied: str,
        review_status: str,
        reviewer_id: str,
        review_reason: str,
        reviewed_at: datetime,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE compliance_evaluations
            SET result = %s,
                consequence_applied = %s,
                review_status = %s,
                reviewer_id = %s,
                review_reason = %s,
                reviewed_at = %s
            WHERE id = %s
            """,
            (
                result,
                consequence_applied,
                review_status,
                reviewer_id,
                review_reason,
                reviewed_at,
                evaluation_id,
            ),
        )
        return cursor.rowcount

    def list_current_roster_members_by_chapter(
        self,
        *,
        chapter_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_current_roster_members_by_chapter_on(
                connection,
                chapter_id=chapter_id,
                limit=limit,
            )

    def _list_current_roster_members_by_chapter_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT r.id,
                   r.member_id,
                   r.status
            FROM roster_entries AS r
            WHERE r.chapter_id = %s
              AND r.status != 'removed'
            ORDER BY r.member_id ASC, r.updated_at DESC, r.id DESC
        """
        params: list[Any] = [chapter_id]
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(sql, tuple(params)).fetchall()


__all__ = ["ComplianceRepository"]
