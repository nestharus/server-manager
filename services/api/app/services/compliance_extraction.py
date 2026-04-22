from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import EvidenceSubmissionNotFoundError
from app.contracts.compliance_extraction import EvidenceExtractionRead
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.infrastructure.ocr import OcrProvider, OcrProviderNotConfiguredError
from app.repositories import compliance as compliance_repo
from app.repositories.db import PostgresDatabase
from app.services.authority import _require_scoped_authority
from app.services.mutations import mutate_entity


logger = logging.getLogger(__name__)

GENERIC_EXTRACTION_ERROR_MESSAGE = "OCR extraction failed"

AUDIT_ACTION_TYPE: dict[str, str] = {
    "evidence_extract": "evidence_submission.extract",
}
AUDIT_CHANGE_TYPE: dict[str, str] = {
    "evidence_extracted": "evidence_submission.extracted",
    "evidence_extract_failed": "evidence_submission.extract_failed",
}
EVIDENCE_EXTRACT_PAYLOAD_ALLOWLIST = frozenset(
    {
        "attachment_ref",
        "rule_hint",
        "extraction_status",
        "raw_text_present",
    }
)


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=None,
        request_surface=request_surface,
    )


def trigger_extraction(
    db: PostgresDatabase,
    evidence_id: UUID,
    *,
    actor: ActorIdentity,
    ocr_provider: OcrProvider,
) -> tuple[EvidenceExtractionRead, MutationResult]:
    with db.connection() as connection:
        current_row = compliance_repo.get_evidence(connection, evidence_id)
        if current_row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        rule_row = compliance_repo.get_rule(connection, current_row["rule_id"])

    _require_scoped_authority(
        "compliance_evidence.extract",
        scope_kind="chapter",
        scope_id=current_row["chapter_id"],
        actor=actor,
        db=db,
    )

    if rule_row is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)

    try:
        extraction = asyncio.run(
            ocr_provider.extract(
                current_row["attachment_ref"],
                rule_hint=rule_row["name"],
            )
        )
    except OcrProviderNotConfiguredError:
        raise
    except Exception as error:
        logger.exception(
            "OCR extraction failed evidence=%s chapter=%s provider_error=%s",
            evidence_id,
            current_row["chapter_id"],
            error,
        )
        result = _persist_extraction_failure(
            db,
            evidence_id=evidence_id,
            expected_version=int(current_row["version"]),
            actor=actor,
            chapter_id=current_row["chapter_id"],
            attachment_ref=current_row["attachment_ref"],
            rule_hint=rule_row["name"],
            error_message=GENERIC_EXTRACTION_ERROR_MESSAGE,
            preserved_raw_text=current_row["raw_text"],
            preserved_extracted_fields=current_row["extracted_fields"],
            preserved_extraction_confidence=current_row["extraction_confidence"],
        )
        with db.connection() as connection:
            failed_row = compliance_repo.get_evidence(connection, evidence_id)
        if failed_row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        return EvidenceExtractionRead.model_validate(failed_row), result

    result = _persist_extraction_success(
        db,
        evidence_id=evidence_id,
        expected_version=int(current_row["version"]),
        actor=actor,
        chapter_id=current_row["chapter_id"],
        attachment_ref=current_row["attachment_ref"],
        rule_hint=rule_row["name"],
        raw_text=extraction.raw_text,
        extracted_fields=extraction.extracted_fields,
        extraction_confidence=extraction.confidence,
    )
    with db.connection() as connection:
        extracted_row = compliance_repo.get_evidence(connection, evidence_id)
    if extracted_row is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)
    return EvidenceExtractionRead.model_validate(extracted_row), result


def _persist_extraction_success(
    db: PostgresDatabase,
    *,
    evidence_id: UUID,
    expected_version: int,
    actor: ActorIdentity,
    chapter_id: str,
    attachment_ref: str,
    rule_hint: str,
    raw_text: str,
    extracted_fields: dict[str, Any],
    extraction_confidence,
) -> MutationResult:
    action_payload = {
        "attachment_ref": attachment_ref,
        "rule_hint": rule_hint,
        "extraction_status": "completed",
        "raw_text_present": True,
    }

    def mutate_projection(connection) -> StateChangeDraft:
        updated_count = compliance_repo.update_evidence_after_extraction(
            connection,
            evidence_id=evidence_id,
            raw_text=raw_text,
            extracted_fields=extracted_fields,
            extraction_status="completed",
            extraction_confidence=extraction_confidence,
            extraction_error=None,
        )
        if updated_count != 1:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        return StateChangeDraft(
            change_type=AUDIT_CHANGE_TYPE["evidence_extracted"],
            payload_json={
                "evidence_id": str(evidence_id),
                "raw_text": raw_text,
                "extracted_fields": extracted_fields,
                "extraction_confidence": str(extraction_confidence),
                "extraction_status": "completed",
            },
        )

    return mutate_entity(
        db=db,
        aggregate_type="evidence_submission",
        aggregate_id=str(evidence_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/compliance/evidence/{evidence_id}/extract",
        ),
        action_type=AUDIT_ACTION_TYPE["evidence_extract"],
        action_payload=action_payload,
        payload_allowlist=set(EVIDENCE_EXTRACT_PAYLOAD_ALLOWLIST),
        mutate_projection=mutate_projection,
        scope_kind="chapter",
        scope_id=chapter_id,
    )


def _persist_extraction_failure(
    db: PostgresDatabase,
    *,
    evidence_id: UUID,
    expected_version: int,
    actor: ActorIdentity,
    chapter_id: str,
    attachment_ref: str,
    rule_hint: str,
    error_message: str,
    preserved_raw_text: str | None,
    preserved_extracted_fields: dict[str, Any] | None,
    preserved_extraction_confidence,
) -> MutationResult:
    action_payload = {
        "attachment_ref": attachment_ref,
        "rule_hint": rule_hint,
        "extraction_status": "failed",
        "raw_text_present": preserved_raw_text is not None,
    }

    def mutate_projection(connection) -> StateChangeDraft:
        updated_count = compliance_repo.update_evidence_after_extraction(
            connection,
            evidence_id=evidence_id,
            raw_text=preserved_raw_text,
            extracted_fields=preserved_extracted_fields,
            extraction_status="failed",
            extraction_confidence=preserved_extraction_confidence,
            extraction_error=error_message,
        )
        if updated_count != 1:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        return StateChangeDraft(
            change_type=AUDIT_CHANGE_TYPE["evidence_extract_failed"],
            payload_json={
                "evidence_id": str(evidence_id),
                "extraction_error": error_message,
                "extraction_status": "failed",
            },
        )

    return mutate_entity(
        db=db,
        aggregate_type="evidence_submission",
        aggregate_id=str(evidence_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/compliance/evidence/{evidence_id}/extract",
        ),
        action_type=AUDIT_ACTION_TYPE["evidence_extract"],
        action_payload=action_payload,
        payload_allowlist=set(EVIDENCE_EXTRACT_PAYLOAD_ALLOWLIST),
        mutate_projection=mutate_projection,
        scope_kind="chapter",
        scope_id=chapter_id,
    )


__all__ = ["trigger_extraction"]
