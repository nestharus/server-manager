from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.settings import Settings
from app.infrastructure.authz import (
    CedarAuthorizationClient,
    CedarAuthorizationRequest,
    CedarAuthorizationUnavailableError,
)


CEDAR_DECISION_ALLOW = "Allow"
PUBLIC_INTAKE_ACTION = 'Action::"application:submit_public"'
PUBLIC_INTAKE_RESOURCE = 'Resource::"server-manager-api:public-applications"'


async def authorize_public_intake(
    _request: Request,
    cedar_authorizer: CedarAuthorizationClient,
    settings: Settings,
) -> None:
    channel = settings.platform_channel
    cedar_request = CedarAuthorizationRequest(
        principal=f'Public::"web-intake.{channel}"',
        action=PUBLIC_INTAKE_ACTION,
        resource=PUBLIC_INTAKE_RESOURCE,
    )
    try:
        decision = cedar_authorizer.is_authorized(cedar_request)
    except CedarAuthorizationUnavailableError as exc:
        raise HTTPException(status_code=503, detail="authorization_unavailable") from exc

    if decision.decision != CEDAR_DECISION_ALLOW:
        raise HTTPException(status_code=403, detail="public_intake_forbidden")
