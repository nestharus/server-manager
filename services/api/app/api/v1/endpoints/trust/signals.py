from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustSignalCreate, TrustSignalRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.authority import AuthorityService
from app.services.trust import TrustService

from ._shared import raise_for_trust_error, require_authority, set_etag


router = APIRouter(prefix="/api/v1/trust/signals")


@router.post("", response_model=TrustSignalRead, status_code=HTTPStatus.CREATED)
@inject
def create_signal(
    body: TrustSignalCreate,
    response: Response,
    service: TrustService = Depends(Provide[ApiContainer.services.trust]),
    authority_service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustSignalRead:
    require_authority(
        authority_service=authority_service,
        actor=actor,
        permission="trust.signal.create",
        scope_kind=body.scope.scope_kind,
        scope_id=body.scope.scope_id,
    )
    try:
        read, result = service.create_trust_signal(body, actor)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, result.etag)
    return read
