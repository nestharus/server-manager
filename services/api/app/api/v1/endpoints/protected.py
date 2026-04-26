from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.contracts.authz import ProtectedAuthzRead
from app.infrastructure.authz import (
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


router = APIRouter(prefix="/api/v1/protected")

CEDAR_ACTION = 'Action::"api:read"'
CEDAR_RESOURCE = 'Resource::"server-manager-api"'


def _identity_from_pomerium(request: Request) -> str:
    for header in (
        "x-pomerium-claim-email",
        "x-pomerium-claim-sub",
        "x-forwarded-email",
    ):
        value = request.headers.get(header)
        if value:
            return value
    raise HTTPException(
        status_code=401,
        detail={
            "code": "identity_missing",
            "message": "Pomerium identity header is required",
        },
    )


@router.get("/authz-proof", response_model=ProtectedAuthzRead)
def authz_proof(request: Request) -> ProtectedAuthzRead:
    subject = _identity_from_pomerium(request)
    cedar_request = CedarAuthorizationRequest(
        principal=f'User::"{subject}"',
        action=CEDAR_ACTION,
        resource=CEDAR_RESOURCE,
    )
    try:
        decision = request.app.state.cedar_authorizer.is_authorized(cedar_request)
    except CedarAuthorizationUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "cedar_unavailable", "message": str(exc)},
        ) from exc

    if decision.decision != "Allow":
        raise HTTPException(
            status_code=403,
            detail={"code": "cedar_denied", "message": "Cedar denied the request"},
        )

    return ProtectedAuthzRead(
        subject=subject,
        action=CEDAR_ACTION,
        resource=CEDAR_RESOURCE,
        decision="Allow",
    )

