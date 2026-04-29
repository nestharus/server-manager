from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.actor import ActorIdentity
from app.contracts.application_messages import ApplicationMessageAppendForbiddenError
from app.contracts.applications import ApplicationNotFoundError
from app.contracts.applications_transcript import ApplicationTranscriptRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.application_transcript import read_application_transcript

from ._shared import get_db


router = APIRouter(prefix="/api/v1/applications")


def _raise_application_transcript_error(error: Exception) -> None:
    if isinstance(error, ApplicationNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "application_not_found", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationMessageAppendForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "application_transcript_forbidden",
                "message": str(error),
            },
        ) from error
    raise error


@router.get(
    "/{application_id}/transcript",
    response_model=ApplicationTranscriptRead,
)
def get_application_transcript_endpoint(
    application_id: UUID,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationTranscriptRead:
    try:
        return read_application_transcript(
            db,
            application_id=application_id,
            viewer_actor_kind=actor.actor_kind,
            viewer_actor_id=actor.actor_id,
        )
    except Exception as error:
        _raise_application_transcript_error(error)

