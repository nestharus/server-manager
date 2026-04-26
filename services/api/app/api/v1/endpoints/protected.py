from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.contracts.authz import AuthzErrorDetail, ProtectedAuthzRead
from app.infrastructure.authz import (
    CedarAuthorizationClient,
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


router = APIRouter(prefix="/api/v1/protected")

CEDAR_ACTION = 'Action::"api:read"'
CEDAR_RESOURCE = 'Resource::"server-manager-api"'
CEDAR_DECISION_ALLOW = "Allow"


def get_pomerium_identity(request: Request) -> str:
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
        detail=AuthzErrorDetail(
            code="identity_missing",
            message="Pomerium identity header is required",
        ).model_dump(),
    )


def get_cedar_authorizer(request: Request) -> CedarAuthorizationClient:
    authorizer = getattr(request.app.state, "cedar_authorizer", None)
    if authorizer is None:
        raise HTTPException(
            status_code=503,
            detail=AuthzErrorDetail(
                code="cedar_unavailable",
                message="Cedar authorizer is not configured",
            ).model_dump(),
        )
    return authorizer


@router.get("/authz-proof", response_model=ProtectedAuthzRead)
def authz_proof(
    subject: str = Depends(get_pomerium_identity),
    cedar_authorizer: CedarAuthorizationClient = Depends(get_cedar_authorizer),
) -> ProtectedAuthzRead:
    cedar_request = CedarAuthorizationRequest(
        principal=f'User::"{subject}"',
        action=CEDAR_ACTION,
        resource=CEDAR_RESOURCE,
    )
    try:
        decision = cedar_authorizer.is_authorized(cedar_request)
    except CedarAuthorizationUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=AuthzErrorDetail(
                code="cedar_unavailable",
                message=str(exc),
            ).model_dump(),
        ) from exc

    if decision.decision != CEDAR_DECISION_ALLOW:
        raise HTTPException(
            status_code=403,
            detail=AuthzErrorDetail(
                code="cedar_denied",
                message="Cedar denied the request",
            ).model_dump(),
        )

    return ProtectedAuthzRead(
        subject=subject,
        action=CEDAR_ACTION,
        resource=CEDAR_RESOURCE,
        decision="Allow",
    )
