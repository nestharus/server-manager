"""Trust profile endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustProfileRead, TrustSignalsInput
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.trust import TrustService

from ._shared import raise_for_trust_error, set_etag


router = APIRouter(prefix="/api/v1/trust")


@router.post(
    "/compute/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("trust.write", "global"))],
)
@inject
def compute_trust(
    member_id: UUID,
    signals: TrustSignalsInput,
    response: Response,
    service: TrustService = Depends(Provide[ApiContainer.services.trust]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustProfileRead:
    try:
        read, result, created = service.compute_trust(member_id, signals, actor)
    except Exception as error:
        raise_for_trust_error(error)

    if not created:
        response.status_code = HTTPStatus.OK
    set_etag(response, result.etag if result is not None else f'"{read.version}"')
    return read


@router.get(
    "/{member_id}",
    response_model=TrustProfileRead,
    dependencies=[Depends(RequireAuthority("trust.read", "global"))],
)
@inject
def get_trust_profile(
    member_id: UUID,
    response: Response,
    service: TrustService = Depends(Provide[ApiContainer.services.trust]),
) -> TrustProfileRead:
    try:
        read, etag = service.get_trust_profile(member_id)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, etag)
    return read
