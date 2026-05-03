from __future__ import annotations

from http import HTTPStatus
from typing import NoReturn
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request, Response

from app.contracts.authority import (
    AuthorityErrorBody,
    DuplicateActiveGrantError,
    GrantAlreadyTransferredError,
    GrantAlreadyRevokedError,
    InvalidHolderIdError,
)
from app.contracts.mutations import StaleMutationError
from app.core.container import ApiContainer
from app.repositories.db import PostgresDatabase
from app.services.read_models import CursorNotSeededError


@inject
def get_db(
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
) -> PostgresDatabase:
    return db


def parse_if_match_strong(request: Request) -> int:
    if_match = request.headers.get("If-Match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail={"code": "if_match_required", "message": "If-Match header required"},
        )
    if (
        len(if_match) < 3
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


def _error_body(
    *,
    code: str,
    message: str,
    existing_grant_id: UUID | None = None,
) -> dict[str, object]:
    return AuthorityErrorBody(
        code=code,  # type: ignore[arg-type]
        message=message,
        existing_grant_id=existing_grant_id,
    ).model_dump(mode="json")


def raise_known_authority_error(error: Exception) -> NoReturn:
    if isinstance(error, LookupError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=_error_body(code="grant_not_found", message=str(error)),
        ) from error
    if isinstance(error, DuplicateActiveGrantError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=_error_body(
                code="duplicate_active_grant",
                message=str(error),
                existing_grant_id=error.existing_grant_id,
            ),
        ) from error
    if isinstance(error, GrantAlreadyRevokedError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=_error_body(code="grant_already_revoked", message=str(error)),
        ) from error
    if isinstance(error, GrantAlreadyTransferredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=_error_body(
                code="grant_already_transferred",
                message=str(error),
                existing_grant_id=error.existing_grant_id,
            ),
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail=_error_body(code="stale_grant_version", message=str(error)),
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=_error_body(code="authority_decision_denied", message=str(error)),
        ) from error
    if isinstance(error, InvalidHolderIdError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=_error_body(code="invalid_holder_id", message=str(error)),
        ) from error
    if isinstance(error, CursorNotSeededError):
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail=_error_body(code="projection_not_initialized", message=str(error)),
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    raise error
