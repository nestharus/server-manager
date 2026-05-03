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
from app.repositories.authority import AuthorityRepository
from app.repositories.db import PostgresDatabase
from app.repositories.ticket_messages import TicketMessagesRepository
from app.repositories.tickets import TicketsRepository
from app.services.authority import current_time, evaluate, _row_to_read


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
    authority_repo = AuthorityRepository(db)
    grants = [
        _row_to_read(row)
        for row in authority_repo.list_grants(
            grantee_id=author_actor_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
    ]
    decision = evaluate(requirement=requirement, grants=grants, at=current_time())
    if not decision.allowed:
        raise TicketMessageAppendForbiddenError("ticket.message.staff authority denied")


class TicketMessagesService:
    def __init__(
        self,
        tickets_repo: TicketsRepository,
        ticket_messages_repo: TicketMessagesRepository,
    ) -> None:
        self.tickets_repo = tickets_repo
        self.ticket_messages_repo = ticket_messages_repo

    def append_ticket_message(
        self,
        *,
        ticket_id: UUID,
        request: TicketMessageAppendRequest,
    ) -> tuple[TicketMessageRead, bool]:
        with self.tickets_repo.db.transaction() as connection:
            return self._append_ticket_message_on(
                connection,
                ticket_id=ticket_id,
                request=request,
            )

    def _append_ticket_message_on(
        self,
        connection: Connection[Any],
        *,
        ticket_id: UUID,
        request: TicketMessageAppendRequest,
    ) -> tuple[TicketMessageRead, bool]:
        if request.client_message_id:
            existing = self.ticket_messages_repo._find_ticket_message_by_client_message_id_on(
                connection,
                ticket_id=ticket_id,
                client_message_id=request.client_message_id,
            )
            if existing is not None:
                return _message_from_row(existing), False

        ticket_row = self.tickets_repo._get_ticket_for_update_on(connection, ticket_id)
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
                self.tickets_repo.db,
                ticket_row=ticket_row,
                author_actor_id=request.author_actor_id,
            )

        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        message_id = uuid4()
        self.ticket_messages_repo._insert_ticket_message_on(
            connection,
            row={
                "id": message_id,
                "ticket_id": ticket_id,
                "message_seq": self.ticket_messages_repo._next_ticket_message_seq_on(
                    connection,
                    ticket_id=ticket_id,
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
        row = self.ticket_messages_repo._get_ticket_message_on(connection, message_id)
        if row is None:
            raise RuntimeError("ticket message insert did not return a readable row")
        return _message_from_row(row), True

    def read_ticket_messages(self, *, ticket_id: UUID) -> list[TicketMessageRead]:
        with self.tickets_repo.db.connection() as connection:
            return self._read_ticket_messages_on(connection, ticket_id=ticket_id)

    def _read_ticket_messages_on(
        self,
        connection: Connection[Any],
        *,
        ticket_id: UUID,
    ) -> list[TicketMessageRead]:
        ticket_row = self.tickets_repo._get_ticket_on(connection, ticket_id)
        if ticket_row is None:
            raise TicketNotFoundError(ticket_id)
        return [
            _message_from_row(row)
            for row in self.ticket_messages_repo._list_ticket_messages_on(
                connection,
                ticket_id=ticket_id,
            )
        ]
