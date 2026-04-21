"""Trust profile endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.members import MemberNotFoundError
from app.contracts.trust import (
    InvalidTrustPolicyError,
    NoTrustPolicyConfiguredError,
    TrustProfileNotFoundError,
    TrustProfileRead,
    TrustSignalsInput,
)
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.trust import (
    compute_trust as compute_trust_service,
    get_trust_profile as get_trust_profile_service,
)


router = APIRouter(prefix="/api/v1/trust")


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


def _set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def _raise_for_trust_error(error: Exception) -> None:
    if isinstance(error, MemberNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "member_not_found", "message": str(error)},
        ) from error
    if isinstance(error, TrustProfileNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "trust_profile_not_found", "message": str(error)},
        ) from error
    if isinstance(error, NoTrustPolicyConfiguredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "no_trust_policy_configured",
                "message": str(error),
            },
        ) from error
    if isinstance(error, InvalidTrustPolicyError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_trust_policy",
                "message": str(error),
            },
        ) from error
    raise error


@router.post(
    "/compute/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("trust.write", "global"))],
)
def compute_trust(
    member_id: UUID,
    signals: TrustSignalsInput,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustProfileRead:
    try:
        read, result, created = compute_trust_service(db, member_id, signals, actor)
    except Exception as error:
        _raise_for_trust_error(error)

    if not created:
        response.status_code = HTTPStatus.OK
    _set_etag(response, result.etag if result is not None else f'"{read.version}"')
    return read


@router.get(
    "/{member_id}",
    response_model=TrustProfileRead,
    dependencies=[Depends(RequireAuthority("trust.read", "global"))],
)
def get_trust_profile(
    member_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
) -> TrustProfileRead:
    try:
        read, etag = get_trust_profile_service(db, member_id)
    except Exception as error:
        _raise_for_trust_error(error)
    _set_etag(response, etag)
    return read
