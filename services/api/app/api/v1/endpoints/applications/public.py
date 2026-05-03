from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request

from app.contracts.applications import (
    PublicApplicationSubmission,
    PublicApplicationSubmissionReceipt,
)
from app.core.container import ApiContainer
from app.core.settings import Settings
from app.infrastructure.authz import CedarAuthorizationClient
from app.services.applicant_discord_auth import verify_applicant_receipt
from app.services.applications import ApplicationsService
from app.services.authorization import authorize_public_intake

from ._shared import raise_known_application_error


router = APIRouter(prefix="/api/v1/public/applications")


@router.post(
    "",
    response_model=PublicApplicationSubmissionReceipt,
    status_code=HTTPStatus.CREATED,
)
@inject
async def submit_public_application_endpoint(
    body: PublicApplicationSubmission,
    request: Request,
    settings: Settings = Depends(Provide[ApiContainer.core.settings]),
    cedar_authorizer: CedarAuthorizationClient = Depends(
        Provide[ApiContainer.infra.cedar_authorizer]
    ),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
) -> PublicApplicationSubmissionReceipt:
    identity = verify_applicant_receipt(
        request,
        signing_key=settings.applicant_receipt_signing_key.get_secret_value(),
    )
    await authorize_public_intake(request, cedar_authorizer, settings)
    try:
        application_id = await service.submit_public_application_with_receipt(
            body,
            discord_user_id=identity.discord_user_id,
        )
    except Exception as error:
        raise_known_application_error(error)
    return PublicApplicationSubmissionReceipt(
        message="Application received",
        application_id=application_id,
    )
