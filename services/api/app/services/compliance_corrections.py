from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import EvidenceSubmissionNotFoundError
from app.contracts.compliance_corrections import (
    CorrectionNotPermittedStatusError,
    OfficerCorrectionRead,
    OfficerCorrectionRequest,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories import compliance as compliance_repo
from app.repositories.db import PostgresDatabase
from app.services.authority import _require_scoped_authority
from app.services.mutations import mutate_entity


AUDIT_ACTION_TYPE: dict[str, str] = {
    "evidence_correct": "evidence_submission.correct",
}
AUDIT_CHANGE_TYPE: dict[str, str] = {
    "evidence_corrected": "evidence_submission.corrected",
}
EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST = frozenset(
    {
        "corrected_fields",
        "correction_reason",
        "corrected_by_member_id",
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


def _officer_correction_from_row(row: dict[str, Any]) -> OfficerCorrectionRead:
    return OfficerCorrectionRead.model_validate(row)


def correct_evidence(
    db: PostgresDatabase,
    evidence_id: UUID,
    request: OfficerCorrectionRequest,
    *,
    expected_version: int,
    actor: ActorIdentity,
) -> tuple[OfficerCorrectionRead, MutationResult]:
    with db.connection() as connection:
        current_row = compliance_repo.get_evidence(connection, evidence_id)
    if current_row is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)

    _require_scoped_authority(
        "compliance_evidence.correct",
        scope_kind="chapter",
        scope_id=current_row["chapter_id"],
        actor=actor,
        db=db,
    )
    if current_row["extraction_status"] not in {"completed", "failed", "corrected"}:
        raise CorrectionNotPermittedStatusError(
            evidence_id=evidence_id,
            extraction_status=current_row["extraction_status"],
        )

    corrected_at = datetime.now(tz=UTC)
    action_payload = {
        "corrected_fields": request.corrected_fields,
        "correction_reason": request.correction_reason,
        "corrected_by_member_id": actor.actor_id,
    }

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = compliance_repo.get_evidence_for_update(connection, evidence_id)
        if row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        if row["extraction_status"] not in {"completed", "failed", "corrected"}:
            raise CorrectionNotPermittedStatusError(
                evidence_id=evidence_id,
                extraction_status=row["extraction_status"],
            )

        updated_count = compliance_repo.update_evidence_correction(
            connection,
            evidence_id=evidence_id,
            corrected_fields=request.corrected_fields,
            corrected_by_member_id=actor.actor_id,
            corrected_at=corrected_at,
            correction_reason=request.correction_reason,
        )
        if updated_count != 1:
            raise EvidenceSubmissionNotFoundError(evidence_id)

        from_overlay = row["extracted_fields_corrected"]
        payload = {
            "evidence_id": str(evidence_id),
            "corrected_by_member_id": actor.actor_id,
            "correction_reason": request.correction_reason,
            "from": {"extracted_fields_corrected": from_overlay},
            "to": {"extracted_fields_corrected": request.corrected_fields},
            "baseline": {"extracted_fields": row["extracted_fields"]},
        }
        return StateChangeDraft(
            change_type=AUDIT_CHANGE_TYPE["evidence_corrected"],
            payload_json=payload,
            diff_json=payload,
        )

    result = mutate_entity(
        db=db,
        aggregate_type="evidence_submission",
        aggregate_id=str(evidence_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/compliance/evidence/{evidence_id}/correct",
            reason_text=request.correction_reason,
        ),
        action_type=AUDIT_ACTION_TYPE["evidence_correct"],
        action_payload=action_payload,
        payload_allowlist=set(EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST),
        mutate_projection=mutate_projection,
        scope_kind="chapter",
        scope_id=current_row["chapter_id"],
    )
    with db.connection() as connection:
        updated_row = compliance_repo.get_evidence(connection, evidence_id)
    if updated_row is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)
    return _officer_correction_from_row(updated_row), result


__all__ = ["correct_evidence"]
