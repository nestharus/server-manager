from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.contracts.actor import ActorIdentity
from app.contracts.application_messages import (
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageAppendRequest,
    ApplicationMessageListRead,
    ApplicationMessageRead,
    ApplicationMessageVisibilityError,
)
from app.contracts.applications import ApplicationNotFoundError
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.application_messages import (
    append_application_message,
    read_application_messages,
)

from ._shared import get_db


router = APIRouter(prefix="/api/v1/applications")


def _raise_application_message_error(error: Exception) -> None:
    if isinstance(error, ApplicationNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "application_not_found", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationMessageVisibilityError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "applicant_visibility_required", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationMessageAppendForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "application_message_forbidden", "message": str(error)},
        ) from error
    raise error


@router.post(
    "/{application_id}/messages",
    response_model=ApplicationMessageRead,
    status_code=HTTPStatus.CREATED,
)
def append_application_message_endpoint(
    application_id: UUID,
    body: ApplicationMessageAppendRequest,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationMessageRead:
    actor_scoped_body = body.model_copy(
        update={
            "author_actor_kind": actor.actor_kind,
            "author_actor_id": actor.actor_id,
        }
    )
    try:
        read, created = append_application_message(
            db,
            application_id=application_id,
            request=actor_scoped_body,
        )
    except Exception as error:
        _raise_application_message_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    return read


@router.get(
    "/{application_id}/messages",
    response_model=ApplicationMessageListRead,
)
def list_application_messages_endpoint(
    application_id: UUID,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationMessageListRead:
    try:
        items = read_application_messages(
            db,
            application_id=application_id,
            viewer_actor_kind=actor.actor_kind,
            viewer_actor_id=actor.actor_id,
        )
    except Exception as error:
        _raise_application_message_error(error)
    return ApplicationMessageListRead(items=items)
