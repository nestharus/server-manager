from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.applications_transcript import ApplicationTranscriptRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.application_transcript import ApplicationTranscriptService

from ._shared import raise_known_application_error


router = APIRouter(prefix="/api/v1/applications")


@router.get(
    "/{application_id}/transcript",
    response_model=ApplicationTranscriptRead,
)
@inject
def get_application_transcript_endpoint(
    application_id: UUID,
    service: ApplicationTranscriptService = Depends(
        Provide[ApiContainer.services.application_transcript]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ApplicationTranscriptRead:
    try:
        return service.read_application_transcript(
            application_id=application_id,
            viewer_actor_kind=actor.actor_kind,
            viewer_actor_id=actor.actor_id,
        )
    except Exception as error:
        raise_known_application_error(error)
