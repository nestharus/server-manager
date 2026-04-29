from __future__ import annotations

from http import HTTPStatus
from typing import NoReturn

from fastapi import HTTPException, Request, Response

from app.contracts.application_messages import (
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageForbiddenError,
)
from app.contracts.applications import (
    ApplicationAlreadyClaimedError,
    ApplicationDecisionReasonRequiredError,
    ApplicationInterviewThreadMismatchError,
    ApplicationListForbiddenError,
    ApplicationNotFoundError,
    ApplicationNotOwnerError,
    ApplicationReactivateOwnerRequiredError,
    ApplicationReviewNotesRequiredError,
    ApplicationWaitlistReasonRequiredError,
    DuplicateApplicationCreateError,
    FormDefinitionNotFoundError,
    InvalidApplicationResponseError,
    InvalidApplicationTransitionError,
)
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.repositories.db import PostgresDatabase


MIN_STRONG_ETAG_LENGTH = 3


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


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


def raise_known_application_error(error: Exception) -> NoReturn:
    if isinstance(error, ApplicationListForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "application_list_forbidden", "message": str(error)},
        ) from error
    if isinstance(error, (FormDefinitionNotFoundError, ApplicationNotFoundError, MissingAggregateError)):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "application_not_found", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_application_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, ApplicationAlreadyClaimedError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "application_already_claimed",
                "message": str(error),
                "current_version": error.application.version,
                "owner_id": (
                    None
                    if error.application.owner_id is None
                    else str(error.application.owner_id)
                ),
            },
        ) from error
    if isinstance(error, ApplicationNotOwnerError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "application_not_owner",
                "message": str(error),
                "current_owner_id": (
                    None
                    if error.current_owner_id is None
                    else str(error.current_owner_id)
                ),
                "actor_id": str(error.actor_id),
            },
        ) from error
    if isinstance(error, ApplicationInterviewThreadMismatchError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "application_interview_thread_mismatch",
                "message": str(error),
                "current_thread_id": error.current_thread_id,
                "requested_thread_id": error.requested_thread_id,
            },
        ) from error
    if isinstance(error, DuplicateApplicationCreateError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "duplicate_application_create",
                "message": str(error),
                "application": error.application.model_dump(mode="json"),
            },
            headers={"etag": f'"{error.application.version}"'},
        ) from error
    if isinstance(error, InvalidApplicationTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_application_transition",
                "message": str(error),
                "from_state": error.from_state,
                "action": error.action,
            },
        ) from error
    if isinstance(error, ApplicationDecisionReasonRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "application_decision_reason_required",
                "message": str(error),
                "action": error.action,
            },
        ) from error
    if isinstance(error, ApplicationReviewNotesRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "application_review_notes_required", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationWaitlistReasonRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "application_waitlist_reason_required", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationReactivateOwnerRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "application_reactivate_owner_required", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationMessageForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "application_transcript_forbidden",
                "message": str(error),
            },
        ) from error
    if isinstance(error, ApplicationMessageAppendForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "application_message_forbidden",
                "message": str(error),
            },
        ) from error
    if isinstance(error, InvalidApplicationResponseError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_application_response", "message": str(error)},
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
