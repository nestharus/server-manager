from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.ticket_messages import TicketMessageAppendRequest, TicketMessageRead
from app.core.dependencies import RequireAuthority
from app.repositories.db import PostgresDatabase
from app.services.ticket_messages import append_ticket_message

from ._shared import get_db, raise_known_ticket_error, service_actor_only

router = APIRouter(prefix="/api/v1/tickets")


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageRead,
    dependencies=[
        Depends(service_actor_only),
        Depends(RequireAuthority("ticket.message.append", "global")),
    ],
)
def append_ticket_message_endpoint(
    ticket_id: UUID,
    body: TicketMessageAppendRequest,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(service_actor_only),
) -> TicketMessageRead:
    try:
        read, created = append_ticket_message(
            db,
            ticket_id=ticket_id,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_ticket_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    return read
