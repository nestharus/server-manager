from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Response

from app.contracts.actor import ActorIdentity
from app.contracts.ticket_messages import TicketMessageListRead
from app.contracts.tickets import TicketRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.ticket_messages import TicketMessagesService
from app.services.tickets import TicketsService

from ._shared import (
    raise_known_ticket_error,
    require_authority_for_grantee,
    set_etag,
    ticket_scope_from_ticket,
)

router = APIRouter(prefix="/api/v1/tickets")


@inject
def _require_ticket_read(
    *,
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity,
    ticket: TicketRead,
) -> bool:
    scope_kind, scope_id = ticket_scope_from_ticket(ticket)
    authority_error: HTTPException | None = None
    try:
        require_authority_for_grantee(
            db,
            grantee_id=actor.actor_id,
            permission="ticket.read",
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        return False
    except HTTPException as error:
        if error.status_code != HTTPStatus.FORBIDDEN:
            raise
        authority_error = error

    if ticket.reporter_id == actor.actor_id and ticket.category_snapshot.privacy_level == "reporter_staff":
        return True
    if ticket.reporter_id == actor.actor_id and ticket.category_snapshot.privacy_level == "staff_only":
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "ticket_read_forbidden", "message": "reporter access is disabled"},
        )
    if authority_error is not None:
        raise authority_error
    raise RuntimeError("ticket read authority check did not produce a decision")


@router.get("/{ticket_id}", response_model=TicketRead)
@inject
def get_ticket_endpoint(
    ticket_id: UUID,
    response: Response,
    service: TicketsService = Depends(Provide[ApiContainer.services.tickets]),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketRead:
    try:
        ticket, etag = service.read_ticket(ticket_id=ticket_id)
    except Exception as error:
        raise_known_ticket_error(error)
    _require_ticket_read(db=db, actor=actor, ticket=ticket)
    set_etag(response, etag)
    return ticket


@router.get("/{ticket_id}/messages", response_model=TicketMessageListRead)
@inject
def list_ticket_messages_endpoint(
    ticket_id: UUID,
    tickets_service: TicketsService = Depends(Provide[ApiContainer.services.tickets]),
    ticket_messages_service: TicketMessagesService = Depends(
        Provide[ApiContainer.services.ticket_messages],
    ),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketMessageListRead:
    try:
        ticket, _etag = tickets_service.read_ticket(ticket_id=ticket_id)
    except Exception as error:
        raise_known_ticket_error(error)
    reporter_access = _require_ticket_read(db=db, actor=actor, ticket=ticket)
    try:
        messages = ticket_messages_service.read_ticket_messages(ticket_id=ticket.id)
    except Exception as error:
        raise_known_ticket_error(error)
    if reporter_access:
        messages = [message for message in messages if message.visibility == "reporter_visible"]
    return TicketMessageListRead(items=messages)
