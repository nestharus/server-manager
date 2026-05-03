from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.tickets import TicketCreate, TicketCreateRead
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority
from app.services.tickets import TicketsService

from ._shared import raise_known_ticket_error, service_actor_only, set_etag

router = APIRouter(prefix="/api/v1/tickets")


@router.post(
    "",
    response_model=TicketCreateRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("ticket.create", "global"))],
)
@inject
def create_ticket_endpoint(
    body: TicketCreate,
    response: Response,
    service: TicketsService = Depends(Provide[ApiContainer.services.tickets]),
    actor: ActorIdentity = Depends(service_actor_only),
) -> TicketCreateRead:
    try:
        created, result = service.create_ticket(body, actor)
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return created
