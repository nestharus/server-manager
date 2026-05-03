from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.applications import (
    PublicApplicationSubmission,
    PublicApplicationSubmissionReceipt,
)
from app.core.container import ApiContainer
from app.services.applicant_discord_auth import (
    DiscordIdentity,
    verify_applicant_receipt,
)
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
    identity: DiscordIdentity = Depends(verify_applicant_receipt),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    _authz: None = Depends(authorize_public_intake),
) -> PublicApplicationSubmissionReceipt:
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
