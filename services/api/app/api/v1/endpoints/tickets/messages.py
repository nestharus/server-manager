from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.ticket_messages import TicketMessageAppendRequest, TicketMessageRead
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority
from app.services.ticket_messages import TicketMessagesService

from ._shared import raise_known_ticket_error, service_actor_only

router = APIRouter(prefix="/api/v1/tickets")


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageRead,
    dependencies=[
        Depends(service_actor_only),
        Depends(RequireAuthority("ticket.message.append", "global")),
    ],
)
@inject
def append_ticket_message_endpoint(
    ticket_id: UUID,
    body: TicketMessageAppendRequest,
    response: Response,
    service: TicketMessagesService = Depends(
        Provide[ApiContainer.services.ticket_messages],
    ),
) -> TicketMessageRead:
    try:
        read, created = service.append_ticket_message(
            ticket_id=ticket_id,
            request=body,
        )
    except Exception as error:
        raise_known_ticket_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    return read
