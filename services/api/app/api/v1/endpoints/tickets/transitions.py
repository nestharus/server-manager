from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.tickets import TicketRead, TicketTransitionRequest
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.tickets import read_ticket, transition_ticket

from ._shared import (
    get_db,
    parse_if_match_strong,
    raise_known_ticket_error,
    require_authority_for_grantee,
    set_etag,
    ticket_scope_from_ticket,
)

router = APIRouter(prefix="/api/v1/tickets")


@router.post("/{ticket_id}/transitions", response_model=TicketRead)
def transition_ticket_endpoint(
    ticket_id: UUID,
    body: TicketTransitionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketRead:
    expected_version = parse_if_match_strong(request)
    try:
        current, _etag = read_ticket(db, ticket_id=ticket_id)
    except Exception as error:
        raise_known_ticket_error(error)
    scope_kind, scope_id = ticket_scope_from_ticket(current)
    require_authority_for_grantee(
        db,
        grantee_id=actor.actor_id,
        permission="ticket.transition",
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    try:
        read, result = transition_ticket(
            db,
            ticket_id=ticket_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return read
