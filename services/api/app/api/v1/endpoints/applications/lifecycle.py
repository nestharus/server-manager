from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity, ActorIdentityMissingError
from app.contracts.applications import (
    ApplicationListForbiddenError,
    ApplicationListRead,
    ApplicationRead,
    ApplicationState,
    ApplicationSubmission,
    ApplicationTransitionRequest,
)
from app.core.dependencies import get_current_actor
from app.core.context import get_current_actor as get_context_actor
from app.repositories.db import PostgresDatabase
from app.services.applications import (
    list_applications,
    read_application,
    require_application_read_authority,
    submit_application,
    transition_application,
)

from ._shared import get_db, parse_if_match_strong, raise_known_application_error, set_etag


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
def submit_application_endpoint(
    body: ApplicationSubmission,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_submit_actor),
) -> ApplicationRead:
    try:
        read, result = submit_application(db, body, actor)
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
def list_applications_endpoint(
    state: str | None = None,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    owner_id: UUID | None = None,
    limit: int = 50,
    after_id: UUID | None = None,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationListRead:
    states = _parse_application_states(state)
    try:
        return list_applications(
            db,
            actor=actor,
            states=states,
            scope_kind=scope_kind,
            scope_id=scope_id,
            owner_id=owner_id,
            limit=limit,
            after_id=after_id,
        )
    except ApplicationListForbiddenError as error:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "application_list_forbidden", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error


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
