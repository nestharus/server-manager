from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationInterviewRequest,
    ApplicationReactivateRequest,
    ApplicationRead,
    ApplicationWaitlistRequest,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.applications import (
    reactivate_application,
    request_interview,
    waitlist_application,
)

from ._shared import get_db, parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/applications")


@router.post(
    "/{application_id}/interview",
    response_model=ApplicationRead,
    status_code=HTTPStatus.OK,
)
def request_interview_endpoint(
    application_id: UUID,
    body: ApplicationInterviewRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = request_interview(
            db,
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
def waitlist_application_endpoint(
    application_id: UUID,
    body: ApplicationWaitlistRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = waitlist_application(
            db,
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
def reactivate_application_endpoint(
    application_id: UUID,
    body: ApplicationReactivateRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, etag = reactivate_application(
            db,
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read
