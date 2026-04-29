from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.applications_transcript import ApplicationTranscriptRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.application_transcript import read_application_transcript

from ._shared import get_db, raise_known_application_error


router = APIRouter(prefix="/api/v1/applications")


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
        raise_known_application_error(error)
