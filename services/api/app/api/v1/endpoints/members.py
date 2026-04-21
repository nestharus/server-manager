"""Member aggregate endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.members import (
    InvalidMemberStatusTransitionError,
    MemberCreate,
    MemberNotFoundError,
    MemberRead,
    MemberStatusPatch,
)
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.members import (
    create_or_get_member as create_or_get_member_service,
    get_member_by_discord_id as get_member_by_discord_id_service,
    get_member_by_id as get_member_by_id_service,
    patch_member_status as patch_member_status_service,
)


router = APIRouter(prefix="/api/v1/members")


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


def _parse_if_match(request: Request) -> int:
    if_match = request.headers.get("if-match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail={"code": "if_match_required", "message": "If-Match header required"},
        )
    if not (if_match.startswith('"') and if_match.endswith('"')):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={"code": "invalid_if_match", "message": "invalid If-Match"},
        )
    try:
        return int(if_match.strip('"'))
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={"code": "invalid_if_match", "message": "invalid If-Match"},
        ) from error


def _set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def _raise_for_member_error(error: Exception) -> None:
    if isinstance(error, (MemberNotFoundError, MissingAggregateError)):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "member_not_found", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_member_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, InvalidMemberStatusTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_member_status_transition",
                "from_status": error.current_status,
                "to_status": error.new_status,
            },
        ) from error
    raise error


@router.post(
    "",
    response_model=MemberRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("member.write", "global"))],
)
def create_member(
    member: MemberCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> MemberRead:
    try:
        read, result, created = create_or_get_member_service(db, member, actor)
    except Exception as error:
        _raise_for_member_error(error)

    if not created:
        response.status_code = HTTPStatus.OK
    _set_etag(response, result.etag if result is not None else f'"{read.version}"')
    return read


@router.get(
    "/by-discord/{discord_user_id}",
    response_model=MemberRead,
    dependencies=[Depends(RequireAuthority("member.read", "global"))],
)
def get_member_by_discord_id(
    discord_user_id: str,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
) -> MemberRead:
    try:
        read, etag = get_member_by_discord_id_service(db, discord_user_id)
    except Exception as error:
        _raise_for_member_error(error)
    _set_etag(response, etag)
    return read


@router.get(
    "/{member_id}",
    response_model=MemberRead,
    dependencies=[Depends(RequireAuthority("member.read", "global"))],
)
def get_member_by_id(
    member_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
) -> MemberRead:
    try:
        read, etag = get_member_by_id_service(db, member_id)
    except Exception as error:
        _raise_for_member_error(error)
    _set_etag(response, etag)
    return read


@router.patch(
    "/{member_id}/status",
    response_model=MemberRead,
    dependencies=[Depends(RequireAuthority("member.write", "global"))],
)
def patch_member_status(
    member_id: UUID,
    patch: MemberStatusPatch,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> MemberRead:
    expected_version = _parse_if_match(request)
    try:
        read, result = patch_member_status_service(
            db,
            member_id,
            patch,
            actor,
            expected_version,
        )
    except Exception as error:
        _raise_for_member_error(error)
    _set_etag(response, result.etag)
    return read
