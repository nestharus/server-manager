from __future__ import annotations

from http import HTTPStatus
from typing import NoReturn

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityRequirement
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.permissions import (
    ExpiredIntentRenewalError,
    InvalidPermissionIntentError,
    NonTemporaryIntentRenewalError,
    PermissionDriftNotFoundError,
    PermissionIntentNotFoundError,
    RenewalExpiresAtInPastError,
)
from app.core.container import ApiContainer
from app.repositories.authority import AuthorityRepository
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, _row_to_read
from app.services.permission_reconciliation import (
    ReconciliationRunConflictError,
    ReconciliationRunNotFoundError,
)
from app.services.permissions import InvalidDriftTransitionError


MIN_STRONG_ETAG_LENGTH = 3


def parse_if_match_strong(request: Request) -> int:
    if_match = request.headers.get("If-Match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail={
                "code": "if_match_required",
                "message": "If-Match header required",
            },
        )
    if (
        len(if_match) < MIN_STRONG_ETAG_LENGTH
        or if_match.startswith("W/")
        or not if_match.startswith('"')
        or not if_match.endswith('"')
    ):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "invalid_if_match",
                "message": "If-Match must be a strong ETag",
            },
        )
    try:
        return int(if_match[1:-1])
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "invalid_if_match",
                "message": "If-Match must be a strong ETag",
            },
        ) from error


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


@inject
def require_scoped(
    actor: ActorIdentity,
    scope_kind: str,
    scope_id: str | None,
    permission: str,
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
) -> None:
    authority_repo = AuthorityRepository(db)
    grants = [
        _row_to_read(row)
        for row in authority_repo.list_grants(
            grantee_id=actor.actor_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
    ]
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


def raise_known_permission_error(error: Exception) -> NoReturn:
    if isinstance(
        error,
        (
            PermissionIntentNotFoundError,
            PermissionDriftNotFoundError,
            ReconciliationRunNotFoundError,
            MissingAggregateError,
        ),
    ):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "not_found", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_permission_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, InvalidDriftTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_drift_transition",
                "message": str(error),
                "from_state": error.from_state,
                "action": error.action,
            },
        ) from error
    if isinstance(error, ReconciliationRunConflictError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "reconciliation_run_conflict",
                "message": str(error),
                "status": error.status,
            },
        ) from error
    if isinstance(error, NonTemporaryIntentRenewalError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "non_temporary_intent",
                "message": str(error),
                "intent_id": str(error.intent_id),
            },
        ) from error
    if isinstance(error, ExpiredIntentRenewalError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "expired_intent",
                "message": str(error),
                "intent_id": str(error.intent_id),
            },
        ) from error
    if isinstance(error, RenewalExpiresAtInPastError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "renewal_expires_at_in_past",
                "message": str(error),
                "intent_id": str(error.intent_id),
            },
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "authority_decision_denied", "message": str(error)},
        ) from error
    if isinstance(error, InvalidPermissionIntentError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    raise error
