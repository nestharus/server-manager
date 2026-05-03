from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.ticket_categories import (
    TicketCategoryCreate,
    TicketCategoryPatch,
    TicketCategoryRead,
)
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.tickets import TicketsService

from ._shared import parse_if_match_strong, raise_known_ticket_error, set_etag

router = APIRouter(prefix="/api/v1/ticket-categories")


@router.post(
    "",
    response_model=TicketCategoryRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("ticket_category.write", "global"))],
)
@inject
def create_ticket_category_endpoint(
    body: TicketCategoryCreate,
    response: Response,
    service: TicketsService = Depends(Provide[ApiContainer.services.tickets]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketCategoryRead:
    try:
        read, result = service.create_category(body, actor)
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return read


@router.patch(
    "/{category_id}",
    response_model=TicketCategoryRead,
    dependencies=[Depends(RequireAuthority("ticket_category.write", "global"))],
)
@inject
def update_ticket_category_endpoint(
    category_id: UUID,
    body: TicketCategoryPatch,
    request: Request,
    response: Response,
    service: TicketsService = Depends(Provide[ApiContainer.services.tickets]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketCategoryRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.update_category(
            category_id,
            expected_version,
            body,
            actor,
        )
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return read
