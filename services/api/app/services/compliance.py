from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.base import validated_update
from app.contracts.compliance import (
    ComplianceEvaluationRead,
    ComplianceRuleCreate,
    ComplianceRuleNotFoundError,
    ComplianceRulePatchEmptyError,
    ComplianceRuleRead,
    ComplianceRuleUpdate,
    ComplianceEvaluationNotFoundError,
    DuplicateActiveComplianceRuleError,
    EvidenceChapterMismatchError,
    EvidenceSubmissionCreate,
    EvidenceSubmissionNotFoundError,
    EvidenceSubmissionRead,
    EvaluationResult,
    SubmittedByMismatchError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.roster import (
    InvalidRosterStatusTransitionError,
    RosterEntryNotFoundError,
    RosterEntryTransitionRequest,
)
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.contracts.authority import InvalidHolderIdError
from app.core.context import (
    get_current_audit_context,
    resolve_register_correlation,
    use_audit_context,
)
from app.services._helpers.authority import (
    _collect_member_aliases,
    _require_scoped_authority,
)


logger = logging.getLogger(__name__)

COMPLIANCE_EVALUATOR_ACTOR_ID = "compliance-evaluator"

AUDIT_ACTION_TYPE: dict[str, str] = {
    "rule_create": "compliance_rule.create",
    "rule_update": "compliance_rule.update",
    "evidence_submit": "evidence_submission.submit",
    "evaluation_create": "compliance_evaluation.create",
}
AUDIT_CHANGE_TYPE: dict[str, str] = {
    "rule_created": "compliance_rule.created",
    "rule_updated": "compliance_rule.updated",
    "evidence_submitted": "evidence_submission.submitted",
    "evaluation_created": "compliance_evaluation.created",
}

RULE_CREATE_PAYLOAD_ALLOWLIST = frozenset(
    {
        "chapter_id",
        "name",
        "cadence_kind",
        "cadence_params",
        "evaluation_window_days",
        "evidence_requirements",
        "consequence_kind",
        "consequence_params",
    }
)
RULE_UPDATE_PAYLOAD_ALLOWLIST = frozenset(
    {
        "name",
        "cadence_kind",
        "cadence_params",
        "evaluation_window_days",
        "evidence_requirements",
        "consequence_kind",
        "consequence_params",
        "active",
    }
)
EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST = frozenset(
    {
        "rule_id",
        "member_id",
        "chapter_id",
        "attachment_ref",
        "submitted_by_member_id",
    }
)
EVALUATION_CREATE_PAYLOAD_ALLOWLIST = frozenset(
    {
        "rule_id",
        "rule_version",
        "chapter_id",
        "member_id",
        "period_start",
        "period_end",
        "result",
        "consequence_applied",
        "review_status",
        "evidence_ids",
    }
)

_ROSTER_AUTO_APPLY_STATUSES = frozenset({"active", "on_leave"})
_FALSE_TEXT_VALUES = frozenset({"0", "false", "no", "off"})


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
    reason_text: str | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=reason_text,
        request_surface=request_surface,
    )


def _rule_from_row(row: dict[str, Any]) -> ComplianceRuleRead:
    return ComplianceRuleRead.model_validate(row)


def _evidence_from_row(row: dict[str, Any]) -> EvidenceSubmissionRead:
    return EvidenceSubmissionRead.model_validate(row)


def _evaluation_from_row(row: dict[str, Any]) -> ComplianceEvaluationRead:
    return ComplianceEvaluationRead.model_validate(row)


def _duplicate_rule_error(
    error: errors.UniqueViolation, *, chapter_id: str, name: str
) -> Exception:
    if (
        getattr(error.diag, "constraint_name", None)
        == "ux_compliance_rules__chapter_active_name"
    ):
        return DuplicateActiveComplianceRuleError(chapter_id, name)
    return error


def _merged_extracted_fields(evidence_row: dict[str, Any]) -> dict[str, Any]:
    extracted = evidence_row.get("extracted_fields")
    merged: dict[str, Any] = {} if extracted is None else dict(extracted)
    corrected = evidence_row.get("extracted_fields_corrected")
    if corrected is not None:
        merged.update(dict(corrected))
    return merged


def _field_is_compliant(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value > 0
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        return stripped.lower() not in _FALSE_TEXT_VALUES
    return value is not None


def _compute_rule_result(
    *,
    rule: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
) -> tuple[EvaluationResult, list[UUID]]:
    if not evidence_rows:
        return "insufficient_evidence", []

    evidence_ids = [row["id"] for row in evidence_rows]
    required_requirements = [
        requirement
        for requirement in rule["evidence_requirements"]
        if requirement.get("required", True)
    ]
    if not required_requirements:
        return "compliant", evidence_ids

    saw_missing = False
    for requirement in required_requirements:
        requirement_type = requirement["type"]
        saw_explicit_failure = False
        satisfied = False
        for evidence_row in evidence_rows:
            merged_fields = _merged_extracted_fields(evidence_row)
            if requirement_type not in merged_fields:
                continue
            if _field_is_compliant(merged_fields[requirement_type]):
                satisfied = True
                break
            saw_explicit_failure = True
        if satisfied:
            continue
        if saw_explicit_failure:
            return "violation", evidence_ids
        saw_missing = True

    if saw_missing:
        return "insufficient_evidence", evidence_ids
    return "compliant", evidence_ids


def _compute_consequence_shape(
    *,
    rule: dict[str, Any],
    result: EvaluationResult,
) -> tuple[str, str]:
    if result == "violation" and rule["consequence_kind"] == "review":
        return "review_queued", "pending"

    if result == "violation" and rule["consequence_kind"] == "under_review":
        if bool(rule["consequence_params"].get("auto_apply", False)):
            return "under_review_applied", "not_required"
        if bool(rule["consequence_params"].get("require_review", True)):
            return "none", "pending"
        return "none", "not_required"

    if bool(rule["consequence_params"].get("require_review", False)):
        return "none", "pending"
    return "none", "not_required"


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, delta_months: int) -> date:
    month_index = (value.year * 12 + value.month - 1) + delta_months
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _quarter_start(value: date) -> date:
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, quarter_month, 1)


def _compute_period(
    *,
    cadence_kind: str,
    cadence_params: dict[str, Any],
    evaluation_window_days: int,
    now: datetime,
) -> tuple[date, date]:
    anchor = (now.astimezone(UTC) - timedelta(days=evaluation_window_days)).date()
    if cadence_kind == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        start = start + timedelta(weeks=int(cadence_params.get("week_offset", 0)))
        return start, start + timedelta(days=6)
    if cadence_kind == "monthly":
        start = _month_start(anchor)
        start = _add_months(start, int(cadence_params.get("month_offset", 0)))
        return start, _add_months(start, 1) - timedelta(days=1)
    if cadence_kind == "quarterly":
        start = _quarter_start(anchor)
        start = _add_months(start, int(cadence_params.get("quarter_offset", 0)) * 3)
        return start, _add_months(start, 3) - timedelta(days=1)
    raise ValueError(f"unsupported cadence_kind {cadence_kind}")


def compliance_evaluator_actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="service", actor_id=COMPLIANCE_EVALUATOR_ACTOR_ID)


def _resolve_submitted_by(
    db: PostgresDatabase,
    *,
    request: EvidenceSubmissionCreate,
    actor: ActorIdentity,
) -> str:
    requested = request.submitted_by_member_id
    if actor.actor_kind == "service":
        return requested if requested is not None else actor.actor_id
    if requested is None or requested == actor.actor_id:
        return actor.actor_id
    with db.connection() as connection:
        try:
            actor_text_aliases, _ = _collect_member_aliases(
                connection,
                [actor.actor_id],
                members_repo=MembersRepository(db),
            )
        except InvalidHolderIdError:
            actor_text_aliases = [actor.actor_id]
    if requested not in actor_text_aliases:
        raise SubmittedByMismatchError(
            actor_id=actor.actor_id,
            submitted_by_member_id=requested,
        )
    return requested


class ComplianceService:
    def __init__(self, compliance_repo, roster_service, mutations_callable) -> None:
        self._compliance_repo = compliance_repo
        self._roster_service = roster_service
        self._mutations_callable = mutations_callable

    def _get_rule_read_unchecked(self, *, rule_id: UUID) -> ComplianceRuleRead:
        row = self._compliance_repo.get_rule(rule_id)
        if row is None:
            raise ComplianceRuleNotFoundError(rule_id)
        return _rule_from_row(row)

    def _get_evidence_submission_unchecked(
        self,
        *,
        evidence_id: UUID,
    ) -> EvidenceSubmissionRead:
        row = self._compliance_repo.get_evidence(evidence_id)
        if row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        return _evidence_from_row(row)

    def create_rule(
        self,
        request: ComplianceRuleCreate,
        *,
        actor: ActorIdentity,
    ) -> tuple[ComplianceRuleRead, MutationResult]:
        db = self._compliance_repo.db
        _require_scoped_authority(
            "compliance_rule.write",
            scope_kind="chapter",
            scope_id=request.chapter_id,
            actor=actor,
            db=db,
        )

        rule_id = uuid4()
        request_payload = request.model_dump(mode="json")

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._compliance_repo._insert_rule_on(
                connection,
                row={
                    "id": rule_id,
                    "chapter_id": request.chapter_id,
                    "name": request.name,
                    "cadence_kind": request.cadence_kind,
                    "cadence_params": request.cadence_params,
                    "evaluation_window_days": request.evaluation_window_days,
                    "evidence_requirements": [
                        requirement.model_dump(mode="json")
                        for requirement in request.evidence_requirements
                    ],
                    "consequence_kind": request.consequence_kind,
                    "consequence_params": request.consequence_params,
                    "active": True,
                    "archived_at": None,
                },
            )
            return StateChangeDraft(
                change_type=AUDIT_CHANGE_TYPE["rule_created"],
                payload_json={
                    "rule_id": str(rule_id),
                    **request_payload,
                    "active": True,
                    "archived_at": None,
                },
            )

        try:
            result = self._mutations_callable(
                connection=None,
                aggregate_type="compliance_rule",
                aggregate_id=str(rule_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface="api:/api/v1/compliance/rules",
                ),
                action_type=AUDIT_ACTION_TYPE["rule_create"],
                action_payload=request_payload,
                payload_allowlist=set(RULE_CREATE_PAYLOAD_ALLOWLIST),
                mutate_projection=mutate_projection,
                scope_kind="chapter",
                scope_id=request.chapter_id,
            )
        except errors.UniqueViolation as error:
            raise _duplicate_rule_error(
                error,
                chapter_id=request.chapter_id,
                name=request.name,
            ) from error
        return self._get_rule_read_unchecked(rule_id=rule_id), result

    def update_rule(
        self,
        rule_id: UUID,
        request: ComplianceRuleUpdate,
        *,
        expected_version: int,
        actor: ActorIdentity,
    ) -> tuple[ComplianceRuleRead, MutationResult]:
        db = self._compliance_repo.db
        current_row = self._compliance_repo.get_rule(rule_id)
        if current_row is None:
            raise ComplianceRuleNotFoundError(rule_id)

        current = _rule_from_row(current_row)
        _require_scoped_authority(
            "compliance_rule.write",
            scope_kind="chapter",
            scope_id=current.chapter_id,
            actor=actor,
            db=db,
        )

        patch = request.model_dump(mode="python", exclude_unset=True)
        if not patch:
            raise ComplianceRulePatchEmptyError()
        if patch.get("active") is False:
            patch["archived_at"] = datetime.now(tz=UTC)
        elif patch.get("active") is True:
            patch["archived_at"] = None
        updated = validated_update(current, patch)
        action_payload = request.model_dump(mode="json", exclude_unset=True)

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            updated_count = self._compliance_repo._update_rule_row_on(
                connection,
                rule_id=rule_id,
                row=updated.model_dump(mode="python"),
            )
            if updated_count != 1:
                raise ComplianceRuleNotFoundError(rule_id)
            return StateChangeDraft(
                change_type=AUDIT_CHANGE_TYPE["rule_updated"],
                payload_json=updated.model_dump(mode="json"),
            )

        try:
            result = self._mutations_callable(
                connection=None,
                aggregate_type="compliance_rule",
                aggregate_id=str(rule_id),
                request=_make_request(
                    expected_version=expected_version,
                    actor=actor,
                    request_surface=f"api:/api/v1/compliance/rules/{rule_id}",
                ),
                action_type=AUDIT_ACTION_TYPE["rule_update"],
                action_payload=action_payload,
                payload_allowlist=set(RULE_UPDATE_PAYLOAD_ALLOWLIST),
                mutate_projection=mutate_projection,
                scope_kind="chapter",
                scope_id=current.chapter_id,
            )
        except errors.UniqueViolation as error:
            raise _duplicate_rule_error(
                error,
                chapter_id=current.chapter_id,
                name=updated.name,
            ) from error
        return self._get_rule_read_unchecked(rule_id=rule_id), result

    def get_rule_read(
        self,
        *,
        rule_id: UUID,
        actor: ActorIdentity,
    ) -> ComplianceRuleRead:
        db = self._compliance_repo.db
        row = self._compliance_repo.get_rule(rule_id)
        if row is None:
            raise ComplianceRuleNotFoundError(rule_id)
        _require_scoped_authority(
            "compliance_rule.read",
            scope_kind="chapter",
            scope_id=row["chapter_id"],
            actor=actor,
            db=db,
        )
        return _rule_from_row(row)

    def list_rules(
        self,
        *,
        chapter_id: str,
        active_only: bool,
        actor: ActorIdentity,
    ) -> list[ComplianceRuleRead]:
        _require_scoped_authority(
            "compliance_rule.read",
            scope_kind="chapter",
            scope_id=chapter_id,
            actor=actor,
            db=self._compliance_repo.db,
        )
        rows = self._compliance_repo.list_rules_by_chapter(
            chapter_id=chapter_id,
            active_only=active_only,
        )
        return [_rule_from_row(row) for row in rows]

    def submit_evidence(
        self,
        request: EvidenceSubmissionCreate,
        *,
        actor: ActorIdentity,
    ) -> tuple[EvidenceSubmissionRead, MutationResult]:
        db = self._compliance_repo.db
        rule_row = self._compliance_repo.get_rule(request.rule_id)
        if rule_row is None:
            raise ComplianceRuleNotFoundError(request.rule_id)
        if request.chapter_id != rule_row["chapter_id"]:
            raise EvidenceChapterMismatchError(
                rule_id=request.rule_id,
                rule_chapter_id=rule_row["chapter_id"],
                request_chapter_id=request.chapter_id,
            )

        _require_scoped_authority(
            "compliance_evidence.submit",
            scope_kind="chapter",
            scope_id=rule_row["chapter_id"],
            actor=actor,
            db=db,
        )

        submitted_by_member_id = _resolve_submitted_by(
            db,
            request=request,
            actor=actor,
        )

        evidence_id = uuid4()
        request_payload = {
            **request.model_dump(mode="json"),
            "submitted_by_member_id": submitted_by_member_id,
        }

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._compliance_repo._insert_evidence_on(
                connection,
                row={
                    "id": evidence_id,
                    "rule_id": request.rule_id,
                    "member_id": request.member_id,
                    "chapter_id": rule_row["chapter_id"],
                    "attachment_ref": request.attachment_ref,
                    "raw_text": None,
                    "extracted_fields": None,
                    "extracted_fields_corrected": None,
                    "extraction_status": "pending",
                    "extraction_confidence": None,
                    "extraction_error": None,
                    "submitted_by_member_id": submitted_by_member_id,
                    "corrected_by_member_id": None,
                    "corrected_at": None,
                    "correction_reason": None,
                },
            )
            return StateChangeDraft(
                change_type=AUDIT_CHANGE_TYPE["evidence_submitted"],
                payload_json={
                    **request_payload,
                    "evidence_id": str(evidence_id),
                    "chapter_id": rule_row["chapter_id"],
                    "extraction_status": "pending",
                },
            )

        result = self._mutations_callable(
            connection=None,
            aggregate_type="evidence_submission",
            aggregate_id=str(evidence_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="api:/api/v1/compliance/evidence",
            ),
            action_type=AUDIT_ACTION_TYPE["evidence_submit"],
            action_payload={
                **request_payload,
                "chapter_id": rule_row["chapter_id"],
            },
            payload_allowlist=set(EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST),
            mutate_projection=mutate_projection,
            scope_kind="chapter",
            scope_id=rule_row["chapter_id"],
        )
        return self._get_evidence_submission_unchecked(evidence_id=evidence_id), result

    def get_evidence_submission(
        self,
        *,
        evidence_id: UUID,
        actor: ActorIdentity,
    ) -> EvidenceSubmissionRead:
        row = self._compliance_repo.get_evidence(evidence_id)
        if row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        _require_scoped_authority(
            "compliance_evidence.read",
            scope_kind="chapter",
            scope_id=row["chapter_id"],
            actor=actor,
            db=self._compliance_repo.db,
        )
        return _evidence_from_row(row)

    def _insert_evaluation_row(
        self,
        connection: Connection[Any],
        *,
        evaluation_id: UUID,
        rule: dict[str, Any],
        member_id: str,
        period_start: date,
        period_end: date,
        result: str,
        consequence_applied: str,
        review_status: str,
        evidence_ids: list[UUID],
    ) -> dict[str, Any] | None:
        return self._compliance_repo._insert_evaluation_if_absent_on(
            connection,
            row={
                "id": evaluation_id,
                "rule_id": rule["id"],
                "rule_version": int(rule["version"]),
                "chapter_id": rule["chapter_id"],
                "member_id": member_id,
                "period_start": period_start,
                "period_end": period_end,
                "result": result,
                "consequence_applied": consequence_applied,
                "review_status": review_status,
                "reviewer_id": None,
                "review_reason": None,
                "reviewed_at": None,
                "evidence_ids": [str(evidence_id) for evidence_id in evidence_ids],
            },
        )

    def _evaluate_member_rule_on(
        self,
        connection: Connection[Any],
        *,
        rule: dict[str, Any],
        member: dict[str, Any],
        period_start: date,
        period_end: date,
        now: datetime,
        actor: ActorIdentity,
        originating_actor: ActorIdentity,
        source: str,
    ) -> ComplianceEvaluationRead | None:
        _ = (now, source)
        evaluation_id = uuid4()
        evidence_rows = self._compliance_repo._list_evidence_for_rule_period_on(
            connection,
            rule_id=rule["id"],
            member_id=member["member_id"],
            period_start=period_start,
            period_end=period_end,
        )
        result, evidence_ids = _compute_rule_result(
            rule=rule,
            evidence_rows=evidence_rows,
        )
        consequence_applied, review_status = _compute_consequence_shape(
            rule=rule,
            result=result,
        )

        roster_entry = None
        if consequence_applied == "under_review_applied":
            try:
                roster_entry, _etag = self._roster_service._get_roster_entry_on(
                    connection,
                    member["id"],
                )
            except RosterEntryNotFoundError:
                roster_entry = None
            if (
                roster_entry is None
                or roster_entry.status not in _ROSTER_AUTO_APPLY_STATUSES
            ):
                consequence_applied = "none"
                review_status = "not_required"
                roster_entry = None

        inserted_row = self._insert_evaluation_row(
            connection,
            evaluation_id=evaluation_id,
            rule=rule,
            member_id=member["member_id"],
            period_start=period_start,
            period_end=period_end,
            result=result,
            consequence_applied=consequence_applied,
            review_status=review_status,
            evidence_ids=evidence_ids,
        )
        if inserted_row is None:
            return None

        if consequence_applied == "under_review_applied" and roster_entry is not None:
            self._roster_service._transition_roster_entry_on(
                connection,
                roster_entry.id,
                RosterEntryTransitionRequest(
                    to_status="under_review",
                    reason="compliance_violation",
                    originating_actor_kind=originating_actor.actor_kind,
                    originating_actor_id=originating_actor.actor_id,
                ),
                actor=actor,
                expected_version=roster_entry.version,
            )

        self._mutations_callable(
            connection=connection,
            aggregate_type="compliance_evaluation",
            aggregate_id=str(evaluation_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="worker:compliance_evaluation",
            ),
            action_type=AUDIT_ACTION_TYPE["evaluation_create"],
            action_payload={
                "rule_id": str(rule["id"]),
                "rule_version": int(rule["version"]),
                "chapter_id": rule["chapter_id"],
                "member_id": member["member_id"],
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "result": result,
                "consequence_applied": consequence_applied,
                "review_status": review_status,
                "evidence_ids": [str(evidence_id) for evidence_id in evidence_ids],
            },
            payload_allowlist=set(EVALUATION_CREATE_PAYLOAD_ALLOWLIST),
            mutate_projection=lambda _active_connection: StateChangeDraft(
                change_type=AUDIT_CHANGE_TYPE["evaluation_created"],
                payload_json={
                    "evaluation_id": str(evaluation_id),
                    "rule_id": str(rule["id"]),
                    "rule_version": int(rule["version"]),
                    "chapter_id": rule["chapter_id"],
                    "member_id": member["member_id"],
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "result": result,
                    "consequence_applied": consequence_applied,
                    "review_status": review_status,
                    "evidence_ids": [str(evidence_id) for evidence_id in evidence_ids],
                },
            ),
            scope_kind="chapter",
            scope_id=rule["chapter_id"],
        )

        evaluation_row = self._compliance_repo._get_evaluation_on(
            connection,
            evaluation_id,
        )
        if evaluation_row is None:
            raise ComplianceEvaluationNotFoundError(evaluation_id)
        return _evaluation_from_row(evaluation_row)

    def run_scheduled_compliance_evaluations(
        self,
        *,
        now: datetime,
        actor: ActorIdentity,
        originating_actor: ActorIdentity | None = None,
        source: str = "worker_sweep",
    ) -> list[ComplianceEvaluationRead]:
        ambient = (
            use_audit_context(resolve_register_correlation(None, allow_new_root=True))
            if get_current_audit_context() is None
            else nullcontext()
        )
        with ambient:
            return self._run_scheduled_compliance_evaluations(
                now=now,
                actor=actor,
                originating_actor=originating_actor,
                source=source,
            )

    def _run_scheduled_compliance_evaluations(
        self,
        *,
        now: datetime,
        actor: ActorIdentity,
        originating_actor: ActorIdentity | None,
        source: str,
    ) -> list[ComplianceEvaluationRead]:
        created: list[ComplianceEvaluationRead] = []
        effective_originating_actor = (
            actor if originating_actor is None else originating_actor
        )
        rules = self._compliance_repo.list_active_rules()

        for rule in rules:
            try:
                period_start, period_end = _compute_period(
                    cadence_kind=rule["cadence_kind"],
                    cadence_params=dict(rule["cadence_params"]),
                    evaluation_window_days=int(rule["evaluation_window_days"]),
                    now=now,
                )
                members = self._compliance_repo.list_current_roster_members_by_chapter(
                    chapter_id=rule["chapter_id"],
                    limit=None,
                )
            except Exception:
                logger.exception(
                    "compliance evaluation failed during rule setup rule=%s source=%s",
                    rule["id"],
                    source,
                )
                continue

            for member in members:
                try:
                    with self._compliance_repo.db.transaction() as connection:
                        evaluation = self._evaluate_member_rule_on(
                            connection,
                            rule=rule,
                            member=member,
                            period_start=period_start,
                            period_end=period_end,
                            now=now,
                            actor=actor,
                            originating_actor=effective_originating_actor,
                            source=source,
                        )
                except InvalidRosterStatusTransitionError:
                    logger.debug(
                        "compliance evaluation skipped invalid roster transition rule=%s member=%s",
                        rule["id"],
                        member["member_id"],
                    )
                    continue
                except Exception:
                    logger.exception(
                        "compliance evaluation failed rule=%s member=%s source=%s",
                        rule["id"],
                        member["member_id"],
                        source,
                    )
                    continue

                if evaluation is not None:
                    created.append(evaluation)

        return created


__all__ = [
    "AUDIT_ACTION_TYPE",
    "AUDIT_CHANGE_TYPE",
    "COMPLIANCE_EVALUATOR_ACTOR_ID",
    "ComplianceService",
    "compliance_evaluator_actor",
]
