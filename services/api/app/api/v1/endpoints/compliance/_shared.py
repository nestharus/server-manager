from __future__ import annotations

from http import HTTPStatus
from typing import NoReturn

from fastapi import HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import (
    ComplianceEvaluationNotFoundError,
    ComplianceRuleNotFoundError,
    ComplianceRulePatchEmptyError,
    DuplicateActiveComplianceRuleError,
    EvaluationReviewNotPermittedError,
    EvidenceChapterMismatchError,
    EvidenceSubmissionNotFoundError,
)
from app.contracts.compliance_corrections import CorrectionNotPermittedStatusError
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.infrastructure.ocr import OcrProvider, OcrProviderNotConfiguredError, StubOcrProvider
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, list_grants_for_grantee
from app.contracts.authority import AuthorityRequirement


MIN_STRONG_ETAG_LENGTH = 3


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


def get_ocr_provider(request: Request) -> OcrProvider:
    provider = getattr(request.app.state, "ocr_provider", None)
    if provider is None:
        provider = StubOcrProvider()
        request.app.state.ocr_provider = provider
    return provider


def parse_if_match_strong(request: Request) -> int:
    if_match = request.headers.get("If-Match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail={"code": "if_match_required", "message": "If-Match header required"},
        )
    if (
        len(if_match) < MIN_STRONG_ETAG_LENGTH
        or if_match.startswith("W/")
        or not if_match.startswith('"')
        or not if_match.endswith('"')
    ):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={"code": "invalid_if_match", "message": "If-Match must be a strong ETag"},
        )
    try:
        return int(if_match[1:-1])
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={"code": "invalid_if_match", "message": "If-Match must be a strong ETag"},
        ) from error


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def require_scoped(
    actor: ActorIdentity,
    db: PostgresDatabase,
    *,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    decision = evaluate(
        requirement=AuthorityRequirement(
            scope_kind=scope_kind,  # type: ignore[arg-type]
            scope_id=scope_id,
            permission=permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise PermissionError("authority requirement denied")


def raise_known_compliance_error(error: Exception) -> NoReturn:
    if isinstance(
        error,
        (
            ComplianceRuleNotFoundError,
            EvidenceSubmissionNotFoundError,
            ComplianceEvaluationNotFoundError,
            MissingAggregateError,
        ),
    ):
        if isinstance(error, ComplianceRuleNotFoundError):
            code = "compliance_rule_not_found"
        elif isinstance(error, EvidenceSubmissionNotFoundError):
            code = "evidence_submission_not_found"
        else:
            code = "compliance_evaluation_not_found"
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": code, "message": str(error)},
        ) from error
    if isinstance(error, DuplicateActiveComplianceRuleError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "duplicate_active_compliance_rule", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_compliance_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, EvidenceChapterMismatchError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "evidence_chapter_mismatch",
                "message": str(error),
                "rule_id": str(error.rule_id),
                "rule_chapter_id": error.rule_chapter_id,
                "request_chapter_id": error.request_chapter_id,
            },
        ) from error
    if isinstance(error, ComplianceRulePatchEmptyError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "compliance_rule_patch_empty", "message": str(error)},
        ) from error
    if isinstance(error, (CorrectionNotPermittedStatusError, EvaluationReviewNotPermittedError)):
        code = (
            "correction_not_permitted_status"
            if isinstance(error, CorrectionNotPermittedStatusError)
            else "evaluation_review_not_permitted"
        )
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": code, "message": str(error)},
        ) from error
    if isinstance(error, OcrProviderNotConfiguredError):
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail={"code": "ocr_provider_not_configured", "message": str(error)},
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "authority_decision_denied", "message": str(error)},
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    raise error
