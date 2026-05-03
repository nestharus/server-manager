from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import (
    ComplianceEvaluationNotFoundError,
    ComplianceEvaluationRead,
    ComplianceEvaluationReviewRequest,
    ComplianceRuleNotFoundError,
    EvaluationReviewNotPermittedError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.roster import RosterEntryTransitionRequest
from app.services._helpers.authority import _require_scoped_authority
from app.services.compliance import (
    _compute_consequence_shape,
    _evaluation_from_row,
)


AUDIT_ACTION_TYPE: dict[str, str] = {
    "review": "compliance_evaluation.review",
    "override": "compliance_evaluation.override",
}
AUDIT_CHANGE_TYPE: dict[str, str] = {
    "reviewed": "compliance_evaluation.reviewed",
    "overridden": "compliance_evaluation.overridden",
}
COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST = frozenset(
    {
        "evaluation_id",
        "reviewer_reason",
        "review_status",
    }
)
COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST = frozenset(
    {
        "evaluation_id",
        "override_result",
        "reviewer_reason",
    }
)


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


def _resolved_review_consequence(
    *,
    rule: dict[str, Any],
    result: str,
    current_consequence_applied: str,
) -> str:
    if (
        result == "violation"
        and rule["consequence_kind"] == "under_review"
        and current_consequence_applied == "none"
    ):
        return "under_review_applied"
    return current_consequence_applied


class ComplianceReviewService:
    def __init__(self, compliance_repo, roster_service, mutations_callable) -> None:
        self._compliance_repo = compliance_repo
        self._roster_service = roster_service
        self._mutations_callable = mutations_callable

    def get_evaluation(
        self,
        evaluation_id: UUID,
        *,
        actor: ActorIdentity,
    ) -> ComplianceEvaluationRead:
        row = self._compliance_repo.get_evaluation(evaluation_id)
        if row is None:
            raise ComplianceEvaluationNotFoundError(evaluation_id)
        _require_scoped_authority(
            "compliance_evaluation.read",
            scope_kind="chapter",
            scope_id=row["chapter_id"],
            actor=actor,
            db=self._compliance_repo.db,
        )
        return _evaluation_from_row(row)

    def _get_evaluation_unchecked(self, evaluation_id: UUID) -> ComplianceEvaluationRead:
        row = self._compliance_repo.get_evaluation(evaluation_id)
        if row is None:
            raise ComplianceEvaluationNotFoundError(evaluation_id)
        return _evaluation_from_row(row)

    def review_evaluation(
        self,
        evaluation_id: UUID,
        request: ComplianceEvaluationReviewRequest,
        *,
        expected_version: int,
        actor: ActorIdentity,
    ) -> tuple[ComplianceEvaluationRead, MutationResult]:
        with self._compliance_repo.db.connection() as connection:
            current_row = self._compliance_repo._get_evaluation_on(
                connection,
                evaluation_id,
            )
            if current_row is None:
                raise ComplianceEvaluationNotFoundError(evaluation_id)
            rule_row = self._compliance_repo._get_rule_on(
                connection,
                current_row["rule_id"],
            )

        _require_scoped_authority(
            "compliance_evaluation.review",
            scope_kind="chapter",
            scope_id=current_row["chapter_id"],
            actor=actor,
            db=self._compliance_repo.db,
        )
        if request.action == "approve" and current_row["review_status"] != "pending":
            raise EvaluationReviewNotPermittedError(
                evaluation_id=evaluation_id,
                review_status=current_row["review_status"],
                action=request.action,
            )
        if request.action == "override" and current_row["review_status"] == "overridden":
            raise EvaluationReviewNotPermittedError(
                evaluation_id=evaluation_id,
                review_status=current_row["review_status"],
                action=request.action,
            )
        if rule_row is None:
            raise ComplianceRuleNotFoundError(current_row["rule_id"])

        reviewed_at = datetime.now(tz=UTC)
        if request.action == "approve":
            next_result = current_row["result"]
            base_consequence_applied = current_row["consequence_applied"]
            next_review_status = "approved"
            action_type = AUDIT_ACTION_TYPE["review"]
            change_type = AUDIT_CHANGE_TYPE["reviewed"]
            payload_allowlist = COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST
            transition_reason = "compliance_approved_violation"
            action_payload = {
                "evaluation_id": str(evaluation_id),
                "reviewer_reason": request.reviewer_reason,
                "review_status": next_review_status,
            }
        else:
            next_result = request.override_result
            base_consequence_applied, _ignored_review_status = (
                _compute_consequence_shape(
                    rule=rule_row,
                    result=next_result,
                )
            )
            next_review_status = "overridden"
            action_type = AUDIT_ACTION_TYPE["override"]
            change_type = AUDIT_CHANGE_TYPE["overridden"]
            payload_allowlist = COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST
            transition_reason = "compliance_override_violation"
            action_payload = {
                "evaluation_id": str(evaluation_id),
                "override_result": next_result,
                "reviewer_reason": request.reviewer_reason,
            }

        next_consequence_applied = _resolved_review_consequence(
            rule=rule_row,
            result=str(next_result),
            current_consequence_applied=str(base_consequence_applied),
        )

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            row = self._compliance_repo._get_evaluation_for_update_on(
                connection,
                evaluation_id,
            )
            if row is None:
                raise ComplianceEvaluationNotFoundError(evaluation_id)
            if request.action == "approve" and row["review_status"] != "pending":
                raise EvaluationReviewNotPermittedError(
                    evaluation_id=evaluation_id,
                    review_status=row["review_status"],
                    action=request.action,
                )

            resolved_consequence_applied = str(next_consequence_applied)
            if resolved_consequence_applied == "under_review_applied":
                roster_members = (
                    self._compliance_repo._list_current_roster_members_by_chapter_on(
                        connection,
                        chapter_id=row["chapter_id"],
                        limit=None,
                    )
                )
                roster_member = next(
                    (
                        member
                        for member in roster_members
                        if member["member_id"] == row["member_id"]
                    ),
                    None,
                )
                if roster_member is not None:
                    roster_entry, _etag = self._roster_service._get_roster_entry_on(
                        connection,
                        roster_member["id"],
                    )
                    if roster_entry.status in {"active", "on_leave"}:
                        self._roster_service._transition_roster_entry_on(
                            connection,
                            roster_member["id"],
                            RosterEntryTransitionRequest(
                                to_status="under_review",
                                reason=transition_reason,
                                originating_actor_kind=actor.actor_kind,
                                originating_actor_id=actor.actor_id,
                            ),
                            actor=actor,
                            expected_version=roster_entry.version,
                        )
                    else:
                        resolved_consequence_applied = "none"
                else:
                    resolved_consequence_applied = "none"

            updated_count = self._compliance_repo._update_evaluation_review_on(
                connection,
                evaluation_id=evaluation_id,
                result=str(next_result),
                consequence_applied=resolved_consequence_applied,
                review_status=next_review_status,
                reviewer_id=actor.actor_id,
                review_reason=request.reviewer_reason,
                reviewed_at=reviewed_at,
            )
            if updated_count != 1:
                raise ComplianceEvaluationNotFoundError(evaluation_id)
            return StateChangeDraft(
                change_type=change_type,
                payload_json={
                    "evaluation_id": str(evaluation_id),
                    "result": next_result,
                    "consequence_applied": resolved_consequence_applied,
                    "review_status": next_review_status,
                    "reviewer_id": actor.actor_id,
                    "review_reason": request.reviewer_reason,
                },
            )

        result = self._mutations_callable(
            connection=None,
            aggregate_type="compliance_evaluation",
            aggregate_id=str(evaluation_id),
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/compliance/evaluations/{evaluation_id}/review",
                reason_text=request.reviewer_reason,
            ),
            action_type=action_type,
            action_payload=action_payload,
            payload_allowlist=set(payload_allowlist),
            mutate_projection=mutate_projection,
            scope_kind="chapter",
            scope_id=current_row["chapter_id"],
        )
        return self._get_evaluation_unchecked(evaluation_id), result


__all__ = ["ComplianceReviewService"]
