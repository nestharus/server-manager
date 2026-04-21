from __future__ import annotations

from http import HTTPStatus

from fastapi import HTTPException, Request, Response

from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.ticket_categories import (
    InvalidTicketSlaRulesError,
    InvalidTicketStateMachineError,
    TicketCategoryNotFoundError,
    TicketCategoryPatchEmptyError,
)
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
        or not if_match.startswith('"')
        or not if_match.endswith('"')
    ):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        )
    try:
        return int(if_match[1:-1])
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        ) from error


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def raise_known_ticket_error(error: Exception) -> None:
    if isinstance(error, (TicketCategoryNotFoundError, MissingAggregateError)):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "ticket_category_not_found", "message": str(error)},
        ) from error
    if isinstance(error, TicketCategoryPatchEmptyError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "ticket_category_patch_empty", "message": str(error)},
        ) from error
    if isinstance(error, InvalidTicketStateMachineError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_state_machine", "message": str(error)},
        ) from error
    if isinstance(error, InvalidTicketSlaRulesError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_sla_rules", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_ticket_category_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    raise error
