from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationRead,
    ApplicationSubmission,
    ApplicationTransitionRequest,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.applications import (
    read_application,
    require_application_read_authority,
    submit_application,
    transition_application,
)

from ._shared import get_db, parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/applications")


@router.post("", response_model=ApplicationRead, status_code=HTTPStatus.CREATED)
def submit_application_endpoint(
    body: ApplicationSubmission,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    try:
        read, result = submit_application(db, body, actor)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application_endpoint(
    application_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    try:
        read, etag = read_application(db, application_id=application_id)
        require_application_read_authority(db, actor=actor, application=read)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read


@router.post("/{application_id}/transitions", response_model=ApplicationRead)
def transition_application_endpoint(
    application_id: UUID,
    body: ApplicationTransitionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = transition_application(
            db,
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read
