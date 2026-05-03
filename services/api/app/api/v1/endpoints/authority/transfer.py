from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityGrantRead, AuthorityGrantTransferRequest
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.authority import AuthorityService

from ._shared import parse_if_match_strong, raise_known_authority_error, set_etag


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("/{grant_id}/transfer", response_model=AuthorityGrantRead)
@inject
def transfer_authority_grant_endpoint(
    grant_id: UUID,
    body: AuthorityGrantTransferRequest,
    request: Request,
    response: Response,
    service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result, created = service.transfer_authority_grant(
            grant_id=grant_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_authority_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    set_etag(response, result.etag)
    return read
