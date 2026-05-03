from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationInterviewRequest,
    ApplicationReactivateRequest,
    ApplicationRead,
    ApplicationWaitlistRequest,
)
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.applications import ApplicationsService

from ._shared import parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/applications")


@router.post(
    "/{application_id}/interview",
    response_model=ApplicationRead,
    status_code=HTTPStatus.OK,
)
@inject
def request_interview_endpoint(
    application_id: UUID,
    body: ApplicationInterviewRequest,
    request: Request,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = service.request_interview(
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read

@router.post(
    "/{application_id}/waitlist",
    response_model=ApplicationRead,
    status_code=HTTPStatus.OK,
)
@inject
def waitlist_application_endpoint(
    application_id: UUID,
    body: ApplicationWaitlistRequest,
    request: Request,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = service.waitlist_application(
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read


@router.post(
    "/{application_id}/reactivate",
    response_model=ApplicationRead,
    status_code=HTTPStatus.OK,
)
@inject
def reactivate_application_endpoint(
    application_id: UUID,
    body: ApplicationReactivateRequest,
    request: Request,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = service.reactivate_application(
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read
