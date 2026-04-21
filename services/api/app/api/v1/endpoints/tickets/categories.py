from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.ticket_categories import (
    TicketCategoryCreate,
    TicketCategoryPatch,
    TicketCategoryRead,
)
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.ticket_categories import create_ticket_category, update_ticket_category

from ._shared import get_db, parse_if_match_strong, raise_known_ticket_error, set_etag

router = APIRouter(prefix="/api/v1/ticket-categories")


@router.post(
    "",
    response_model=TicketCategoryRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("ticket_category.write", "global"))],
)
def create_ticket_category_endpoint(
    body: TicketCategoryCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketCategoryRead:
    try:
        read, result = create_ticket_category(db, body, actor)
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return read


@router.patch(
    "/{category_id}",
    response_model=TicketCategoryRead,
    dependencies=[Depends(RequireAuthority("ticket_category.write", "global"))],
)
def update_ticket_category_endpoint(
    category_id: UUID,
    body: TicketCategoryPatch,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TicketCategoryRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = update_ticket_category(
            db,
            category_id,
            expected_version,
            body,
            actor,
        )
    except Exception as error:
        raise_known_ticket_error(error)
    set_etag(response, result.etag)
    return read
