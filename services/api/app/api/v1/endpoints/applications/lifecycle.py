from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity, ActorIdentityMissingError
from app.contracts.applications import (
    ApplicationListRead,
    ApplicationRead,
    ApplicationState,
    ApplicationSubmission,
    ApplicationTransitionRequest,
)
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.core.context import get_current_actor as get_context_actor
from app.services.applications import ApplicationsService

from ._shared import parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/applications")


def get_submit_actor() -> ActorIdentity:
    try:
        return get_context_actor()
    except ActorIdentityMissingError as error:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail={
                "detail": {
                    "code": "actor_identity_missing",
                    "message": error.message,
                }
            },
        ) from error


@router.post("", response_model=ApplicationRead, status_code=HTTPStatus.CREATED)
@inject
def submit_application_endpoint(
    body: ApplicationSubmission,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_submit_actor),
) -> ApplicationRead:
    try:
        read, result = service.submit_application(body, actor)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read


def _parse_application_states(state: str | None) -> frozenset[str] | None:
    if state is None:
        return None
    parsed: set[str] = set()
    valid_states = {item.value for item in ApplicationState}
    for raw_state in state.split(","):
        value = raw_state.strip()
        if value not in valid_states:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_application_state",
                    "message": f"invalid application state: {value}",
                },
            )
        parsed.add(value)
    return frozenset(parsed)


@router.get("", response_model=ApplicationListRead)
@inject
def list_applications_endpoint(
    state: str | None = None,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    owner_id: UUID | None = None,
    limit: int = 50,
    after_id: UUID | None = None,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationListRead:
    states = _parse_application_states(state)
    try:
        return service.list_applications(
            actor=actor,
            states=states,
            scope_kind=scope_kind,
            scope_id=scope_id,
            owner_id=owner_id,
            limit=limit,
            after_id=after_id,
        )
    except Exception as error:
        raise_known_application_error(error)


@router.get("/{application_id}", response_model=ApplicationRead)
@inject
def get_application_endpoint(
    application_id: UUID,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    try:
        read, etag = service.read_application(application_id=application_id)
        service.require_application_read_authority(actor=actor, application=read)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read


@router.post("/{application_id}/transitions", response_model=ApplicationRead)
@inject
def transition_application_endpoint(
    application_id: UUID,
    body: ApplicationTransitionRequest,
    request: Request,
    response: Response,
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.transition_application(
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read
