from __future__ import annotations

from fastapi import HTTPException, Request

from app.infrastructure.authz import (
    CedarAuthorizationClient,
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


CEDAR_DECISION_ALLOW = "Allow"
PUBLIC_INTAKE_ACTION = 'Action::"application:submit_public"'
PUBLIC_INTAKE_RESOURCE = 'Resource::"server-manager-api:public-applications"'


def _get_cedar_authorizer(request: Request) -> CedarAuthorizationClient:
    authorizer = getattr(request.app.state, "cedar_authorizer", None)
    if authorizer is None:
        raise HTTPException(status_code=503, detail="authorization_unavailable")
    return authorizer


async def authorize_public_intake(request: Request) -> None:
    settings = getattr(request.app.state, "settings", None)
    channel = getattr(settings, "platform_channel", "local")
    authorizer = _get_cedar_authorizer(request)
    cedar_request = CedarAuthorizationRequest(
        principal=f'Public::"web-intake.{channel}"',
        action=PUBLIC_INTAKE_ACTION,
        resource=PUBLIC_INTAKE_RESOURCE,
    )
    try:
        decision = authorizer.is_authorized(cedar_request)
    except CedarAuthorizationUnavailableError as exc:
        raise HTTPException(status_code=503, detail="authorization_unavailable") from exc

    if decision.decision != CEDAR_DECISION_ALLOW:
        raise HTTPException(status_code=403, detail="public_intake_forbidden")
