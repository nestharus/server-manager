from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustProfileRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.authority import AuthorityService
from app.services.trust import TrustService

from ._shared import raise_for_trust_error, require_authority, set_etag


router = APIRouter(prefix="/api/v1/trust/recompute")


@router.post(
    "/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.OK,
)
@inject
def recompute_trust(
    member_id: UUID,
    response: Response,
    service: TrustService = Depends(Provide[ApiContainer.services.trust]),
    authority_service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustProfileRead:
    require_authority(
        authority_service=authority_service,
        actor=actor,
        permission="trust.recompute",
        scope_kind="member",
        scope_id=str(member_id),
    )
    try:
        read, result = service.recompute_trust_profile(member_id, actor)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, result.etag)
    return read
