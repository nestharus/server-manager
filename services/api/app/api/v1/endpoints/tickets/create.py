from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.ticket_messages import TicketMessageAppendRequest
from app.contracts.tickets import TicketCreate, TicketCreateRead
from app.core.dependencies import RequireAuthority
from app.repositories.db import PostgresDatabase
from app.services.tickets import create_ticket

from ._shared import get_db, raise_known_ticket_error, service_actor_only, set_etag

router = APIRouter(prefix="/api/v1/tickets")


@router.post(
    "",
    response_model=TicketCreateRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(service_actor_only), Depends(RequireAuthority("ticket.create", "global"))],
)
def create_ticket_endpoint(
    body: TicketCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(service_actor_only),
) -> TicketCreateRead:
    request = TicketCreate.model_validate(
        {
            **body.model_dump(mode="python"),
            "initial_message": TicketMessageAppendRequest.model_validate(
                body.initial_message.model_dump(mode="python")
            ),
        }
    )
    try:
        created, result = create_ticket(db, request, actor)
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return created
