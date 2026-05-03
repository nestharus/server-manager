from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.authority import SuccessionPlanRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.authority import AuthorityService

from ._shared import raise_known_authority_error


router = APIRouter(prefix="/api/v1/chapters")


@router.get("/{chapter_id}/succession-plan", response_model=SuccessionPlanRead)
@inject
def get_succession_plan_endpoint(
    chapter_id: str,
    service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> SuccessionPlanRead:
    try:
        return service.compute_succession_plan(chapter_id=chapter_id, actor=actor)
    except Exception as error:
        raise_known_authority_error(error)
