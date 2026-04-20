from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import (
    AuthorityErrorBody,
    AuthorityGrantCreate,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityGrantRevoke,
    DuplicateActiveGrantError,
    GrantAlreadyRevokedError,
)
from app.contracts.mutations import StaleMutationError
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import (
    get_authority_grant,
    grant_authority,
    list_authority_grants,
    revoke_authority,
)


router = APIRouter(prefix="/api/v1/authority-grants")


def _parse_if_match(request: Request) -> int:
    if_match = request.headers.get("if-match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail="If-Match header required",
        )
    if len(if_match) < 3 or not if_match.startswith('"') or not if_match.endswith('"'):
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


def _error_body(
    *,
    code: str,
    message: str,
    existing_grant_id: UUID | None = None,
) -> dict[str, object]:
    return AuthorityErrorBody(
        code=code,
        message=message,
        existing_grant_id=existing_grant_id,
    ).model_dump(mode="json")


def _db(request: Request) -> PostgresDatabase:
    return request.app.state.db


@router.post("", response_model=AuthorityGrantRead, status_code=HTTPStatus.CREATED)
def create_authority_grant(
    body: AuthorityGrantCreate,
    request: Request,
    response: Response,
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    db = _db(request)
    try:
        created = grant_authority(
            db=db,
            grantee_id=body.grantee_id,
            scope_kind=body.scope_kind,
            scope_id=body.scope_id,
            permissions=body.permissions,
            expires_at=body.expires_at,
            predecessor_grant_id=body.predecessor_grant_id,
            actor=(actor.actor_kind, actor.actor_id),
        )
    except DuplicateActiveGrantError as error:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=_error_body(
                code="duplicate_active_grant",
                message=str(error),
                existing_grant_id=error.existing_grant_id,
            ),
        ) from error

    _, etag = get_authority_grant(db, grant_id=created.id)
    response.headers["etag"] = etag
    return created


@router.get("", response_model=AuthorityGrantListRead)
def list_authority_grants_endpoint(
    request: Request,
    grantee_id: str = Query(min_length=1),
    scope_kind: str | None = None,
    scope_id: str | None = None,
    include_revoked: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    after_id: UUID | None = None,
    actor: ActorIdentity = Depends(get_current_actor),  # noqa: ARG001
) -> AuthorityGrantListRead:
    return list_authority_grants(
        _db(request),
        grantee_id=grantee_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        include_revoked=include_revoked,
        limit=limit,
        after_id=after_id,
    )


@router.post("/{grant_id}/revoke", response_model=AuthorityGrantRead)
def revoke_authority_grant(
    grant_id: UUID,
    body: AuthorityGrantRevoke,
    request: Request,
    response: Response,
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    expected_version = _parse_if_match(request)
    db = _db(request)
    try:
        revoked = revoke_authority(
            db=db,
            grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            revoked_by=actor.actor_id,
            reason=body.reason,
            expected_version=expected_version,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=_error_body(code="grant_not_found", message=str(error)),
        ) from error
    except GrantAlreadyRevokedError as error:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=_error_body(code="grant_already_revoked", message=str(error)),
        ) from error
    except StaleMutationError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail=_error_body(code="stale_grant_version", message=str(error)),
        ) from error

    _, etag = get_authority_grant(db, grant_id=revoked.id)
    response.headers["etag"] = etag
    return revoked
