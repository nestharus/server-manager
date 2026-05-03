from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.authority import HandoffResult, LeadershipHandoffRequest
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.leadership_handoff_applications import LeadershipHandoffApplicationsService

from ._shared import raise_known_authority_error


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("/{grant_id}/handoff/applications", response_model=HandoffResult)
@inject
def handoff_applications_endpoint(
    grant_id: UUID,
    body: LeadershipHandoffRequest,
    service: LeadershipHandoffApplicationsService = Depends(
        Provide[ApiContainer.services.leadership_handoff_applications]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> HandoffResult:
    try:
        return service.execute_handoff(grant_id=grant_id, request=body, actor=actor)
    except Exception as error:
        raise_known_authority_error(error)
