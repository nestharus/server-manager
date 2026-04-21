from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.authority import AuthorityRequirement
from app.contracts.ticket_messages import (
    TicketMessageAppendForbiddenError,
    TicketMessageAppendRequest,
    TicketMessageRead,
    TicketMessageVisibilityError,
)
from app.contracts.tickets import TicketNotFoundError
from app.core.context import MissingCorrelationContextError, get_current_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.ticket_messages import (
    find_ticket_message_by_client_message_id,
    get_ticket_message,
    insert_ticket_message,
    list_ticket_messages,
    next_ticket_message_seq,
)
from app.repositories.tickets import get_ticket, get_ticket_for_update
from app.services.authority import current_time, evaluate, list_grants_for_grantee


def _message_from_row(row: dict[str, Any]) -> TicketMessageRead:
    return TicketMessageRead(
        id=row["id"],
        ticket_id=row["ticket_id"],
        message_seq=int(row["message_seq"]),
        author_actor_kind=row["author_actor_kind"],
        author_actor_id=row["author_actor_id"],
        visibility=row["visibility"],
        body_markdown=row["body_markdown"],
        client_message_id=row["client_message_id"],
        correlation_id=row["correlation_id"],
        causation_id=row.get("causation_id"),
        created_at=row["created_at"],
    )


def _ticket_scope(ticket_row: dict[str, Any]) -> tuple[str, str | None]:
    routing_scope = ticket_row["category_snapshot"]["routing_scope"]
    return str(routing_scope["scope_kind"]), routing_scope.get("scope_id")


def _assert_staff_authority(
    db: PostgresDatabase,
    *,
    ticket_row: dict[str, Any],
    author_actor_id: str,
) -> None:
    scope_kind, scope_id = _ticket_scope(ticket_row)
    requirement = AuthorityRequirement(
        scope_kind=scope_kind,  # type: ignore[arg-type]
        scope_id=scope_id,
        permission="ticket.message.staff",
    )
    grants = list_grants_for_grantee(db, grantee_id=author_actor_id)
    decision = evaluate(requirement=requirement, grants=grants, at=current_time())
    if not decision.allowed:
        raise TicketMessageAppendForbiddenError("ticket.message.staff authority denied")


def append_ticket_message(
    db: PostgresDatabase,
    *,
    ticket_id: UUID,
    request: TicketMessageAppendRequest,
    connection: Connection[Any] | None = None,
) -> tuple[TicketMessageRead, bool]:
    def _append(active_connection: Connection[Any]) -> tuple[TicketMessageRead, bool]:
        if request.client_message_id:
            existing = find_ticket_message_by_client_message_id(
                active_connection,
                ticket_id=ticket_id,
                client_message_id=request.client_message_id,
            )
            if existing is not None:
                return _message_from_row(existing), False

        ticket_row = get_ticket_for_update(active_connection, ticket_id)
        if ticket_row is None:
            raise TicketNotFoundError(ticket_id)

        reporter_id = str(ticket_row["reporter_id"])
        is_reporter_authored = (
            request.author_actor_kind == "user"
            and request.author_actor_id == reporter_id
        )

        if is_reporter_authored:
            if request.visibility != "reporter_visible":
                raise TicketMessageVisibilityError(
                    "reporter-authored messages must be reporter_visible"
                )
        else:
            _assert_staff_authority(
                db,
                ticket_row=ticket_row,
                author_actor_id=request.author_actor_id,
            )

        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        message_id = uuid4()
        insert_ticket_message(
            active_connection,
            row={
                "id": message_id,
                "ticket_id": ticket_id,
                "message_seq": next_ticket_message_seq(
                    active_connection, ticket_id=ticket_id
                ),
                "author_actor_kind": request.author_actor_kind,
                "author_actor_id": request.author_actor_id,
                "visibility": request.visibility,
                "body_markdown": request.body_markdown,
                "client_message_id": request.client_message_id,
                "correlation_id": ctx.correlation_id,
                "causation_id": ctx.causation_id,
            },
        )
        row = get_ticket_message(active_connection, message_id)
        if row is None:
            raise RuntimeError("ticket message insert did not return a readable row")
        return _message_from_row(row), True

    if connection is not None:
        return _append(connection)
    with db.transaction() as active_connection:
        return _append(active_connection)


def read_ticket_messages(
    db: PostgresDatabase,
    *,
    ticket_id: UUID,
) -> list[TicketMessageRead]:
    with db.connection() as connection:
        ticket_row = get_ticket(connection, ticket_id)
        if ticket_row is None:
            raise TicketNotFoundError(ticket_id)
        return [
            _message_from_row(row)
            for row in list_ticket_messages(connection, ticket_id=ticket_id)
        ]
