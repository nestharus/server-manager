from __future__ import annotations

from http import HTTPStatus

from fastapi import HTTPException, Response

from app.contracts.actor import ActorIdentity
from app.contracts.members import MemberNotFoundError
from app.contracts.trust import (
    InvalidTrustPolicyError,
    InvalidTrustSignalActorError,
    InvalidTrustSignalScopeError,
    NoTrustPolicyConfiguredError,
    TrustProfileNotFoundError,
    TrustRecomputeConflictError,
)
from app.services.authority import AuthorityService


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def require_authority(
    *,
    authority_service: AuthorityService,
    actor: ActorIdentity,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    try:
        authority_service.require_scoped_authority(
            permission,
            scope_kind=scope_kind,
            scope_id=scope_id,
            actor=actor,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "authority_decision_denied",
                "message": "authority requirement denied",
            },
        ) from error


def raise_for_trust_error(error: Exception) -> None:
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
    if isinstance(error, (InvalidTrustSignalScopeError, InvalidTrustSignalActorError)):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={"code": "invalid_trust_signal", "message": str(error)},
        ) from error
    if isinstance(error, TrustRecomputeConflictError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "trust_recompute_conflict",
                "message": str(error),
            },
        ) from error
    raise error
