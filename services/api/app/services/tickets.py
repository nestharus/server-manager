from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.ticket_messages import TicketMessageRead
from app.contracts.ticket_categories import TicketCategoryNotFoundError
from app.contracts.tickets import (
    DuplicateTicketCreateError,
    InvalidTicketTransitionError,
    TicketCategorySnapshotRead,
    TicketCreate,
    TicketCreateRead,
    TicketNotFoundError,
    TicketRead,
    TicketTransitionOwnerChangeForbiddenError,
    TicketTransitionPriorityChangeForbiddenError,
    TicketTransitionReasonRequiredError,
    TicketTransitionRequest,
    TicketTransitionResolutionRequiredError,
)
from app.repositories.db import PostgresDatabase
from app.repositories.ticket_categories import get_ticket_category_for_update
from app.repositories.ticket_messages import get_first_ticket_message
from app.repositories.tickets import (
    get_ticket,
    get_ticket_by_category_client_ticket_id,
    get_ticket_for_update,
    insert_ticket,
    insert_ticket_transition,
    update_ticket,
)
from app.services.mutations import mutate_entity
from app.services.ticket_messages import append_ticket_message

TICKET_CREATE_PAYLOAD_ALLOWLIST = {
    "category_id",
    "reporter_id",
    "subject_id",
    "priority",
    "client_ticket_id",
    "originating_actor_kind",
    "originating_actor_id",
}
TICKET_TRANSITION_PAYLOAD_ALLOWLIST = {
    "action",
    "to_state",
    "reason",
    "resolution",
    "owner_id",
    "priority",
    "originating_actor_kind",
    "originating_actor_id",
}
DEFAULT_TICKET_PRIORITY = "normal"


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=None,
        request_surface=request_surface,
    )


def _ticket_from_row(row: dict[str, Any]) -> TicketRead:
    return TicketRead(
        id=row["id"],
        category_id=row["category_id"],
        category_version=int(row["category_version"]),
        category_snapshot=TicketCategorySnapshotRead.model_validate(
            row["category_snapshot"]
        ),
        reporter_id=row["reporter_id"],
        subject_id=row["subject_id"],
        state=row["state"],
        priority=row["priority"],
        owner_id=row["owner_id"],
        resolution=row["resolution"],
        terminal_at=row["terminal_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _fetch_ticket_row(connection: Connection[Any], ticket_id: UUID) -> dict[str, Any]:
    row = get_ticket(connection, ticket_id)
    if row is None:
        raise TicketNotFoundError(ticket_id)
    return row


def _resolve_reporter_id(request: TicketCreate) -> str:
    if request.reporter_id is not None:
        return request.reporter_id
    if request.initial_message.author_actor_kind == "user":
        return request.initial_message.author_actor_id
    if request.originating_actor_kind == "user":
        return request.originating_actor_id
    raise ValueError("reporter_id is required for ticket creation")


def _build_category_snapshot(category_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "category_id": str(category_row["id"]),
        "name": category_row["name"],
        "category_version": int(category_row["version"]),
        "routing_scope": deepcopy(category_row["routing_scope"]),
        "privacy_level": category_row["privacy_level"],
        "state_machine": deepcopy(category_row["state_machine"]),
        "sla_rules": deepcopy(category_row["sla_rules"]),
    }


def _transition_edge(
    ticket_row: dict[str, Any],
    request: TicketTransitionRequest,
) -> dict[str, Any]:
    state_machine = ticket_row["category_snapshot"]["state_machine"]
    matches = [
        edge
        for edge in state_machine.get("edges", [])
        if edge["from"] == ticket_row["state"]
        and edge["action"] == request.action
        and edge["to"] == request.to_state
    ]
    if len(matches) != 1:
        raise InvalidTicketTransitionError(
            ticket_id=ticket_row["id"],
            from_state=str(ticket_row["state"]),
            action=request.action,
            to_state=request.to_state,
        )
    return matches[0]


def validate_transition(
    ticket_row: dict[str, Any],
    request: TicketTransitionRequest,
) -> dict[str, Any]:
    edge = _transition_edge(ticket_row, request)
    reason = None if request.reason is None else request.reason.strip()
    resolution = None if request.resolution is None else request.resolution.strip()
    if edge.get("requires_reason") and not reason:
        raise TicketTransitionReasonRequiredError(
            from_state=str(ticket_row["state"]),
            action=request.action,
            to_state=request.to_state,
        )
    if edge.get("requires_resolution") and not resolution:
        raise TicketTransitionResolutionRequiredError(
            from_state=str(ticket_row["state"]),
            action=request.action,
            to_state=request.to_state,
        )
    if request.owner_id is not None and not edge.get("allow_owner_change", False):
        raise TicketTransitionOwnerChangeForbiddenError(
            from_state=str(ticket_row["state"]),
            action=request.action,
            to_state=request.to_state,
        )
    if request.priority is not None and not edge.get("allow_priority_change", False):
        raise TicketTransitionPriorityChangeForbiddenError(
            from_state=str(ticket_row["state"]),
            action=request.action,
            to_state=request.to_state,
        )

    state_map = {
        state["key"]: state for state in ticket_row["category_snapshot"]["state_machine"]["states"]
    }
    next_state = request.to_state
    next_owner_id = request.owner_id if request.owner_id is not None else ticket_row["owner_id"]
    next_priority = request.priority if request.priority is not None else ticket_row["priority"]
    next_resolution = (
        resolution if request.resolution is not None else ticket_row["resolution"]
    )
    next_terminal_at = (
        datetime.now(UTC) if state_map[next_state]["terminal"] else None
    )
    return {
        "edge": edge,
        "reason": reason,
        "resolution": next_resolution,
        "next_state": next_state,
        "next_owner_id": next_owner_id,
        "next_priority": next_priority,
        "next_terminal_at": next_terminal_at,
    }


def _build_transition_diff(
    ticket_row: dict[str, Any],
    validated: dict[str, Any],
) -> dict[str, Any]:
    diff = {
        "state": {
            "old": ticket_row["state"],
            "new": validated["next_state"],
        }
    }
    if ticket_row["owner_id"] != validated["next_owner_id"]:
        diff["owner_id"] = {
            "old": ticket_row["owner_id"],
            "new": validated["next_owner_id"],
        }
    if ticket_row["priority"] != validated["next_priority"]:
        diff["priority"] = {
            "old": ticket_row["priority"],
            "new": validated["next_priority"],
        }
    if ticket_row["resolution"] != validated["resolution"]:
        diff["resolution"] = {
            "old": ticket_row["resolution"],
            "new": validated["resolution"],
        }
    if ticket_row["terminal_at"] != validated["next_terminal_at"]:
        diff["terminal_at"] = {
            "old": (
                None
                if ticket_row["terminal_at"] is None
                else ticket_row["terminal_at"].isoformat()
            ),
            "new": (
                None
                if validated["next_terminal_at"] is None
                else validated["next_terminal_at"].isoformat()
            ),
        }
    return diff


def _load_duplicate_initial_message(
    connection: Connection[Any],
    *,
    ticket_id: UUID,
) -> TicketMessageRead:
    row = get_first_ticket_message(
        connection,
        ticket_id=ticket_id,
    )
    if row is None:
        raise RuntimeError("duplicate ticket create could not find initial message")
    return TicketMessageRead.model_validate(row)


def create_ticket(
    db: PostgresDatabase,
    request: TicketCreate,
    actor: ActorIdentity,
) -> tuple[TicketCreateRead, MutationResult]:
    reporter_id = _resolve_reporter_id(request)
    ticket_id = uuid4()

    with db.transaction() as connection:
        category_row = get_ticket_category_for_update(connection, request.category_id)
        if category_row is None:
            raise TicketCategoryNotFoundError(request.category_id)

        if request.client_ticket_id is not None:
            existing = get_ticket_by_category_client_ticket_id(
                connection,
                category_id=request.category_id,
                client_ticket_id=request.client_ticket_id,
            )
            if existing is not None:
                existing_read = _ticket_from_row(existing)
                initial_message = _load_duplicate_initial_message(
                    connection,
                    ticket_id=existing_read.id,
                )
                raise DuplicateTicketCreateError(existing_read, initial_message)

        snapshot = _build_category_snapshot(category_row)
        persisted = {
            "category_id": request.category_id,
            "category_version": int(category_row["version"]),
            "category_snapshot": snapshot,
            "reporter_id": reporter_id,
            "subject_id": request.subject_id,
            "state": snapshot["state_machine"]["initial_state"],
            "priority": request.priority or DEFAULT_TICKET_PRIORITY,
            "owner_id": None,
            "resolution": None,
            "client_ticket_id": request.client_ticket_id,
            "terminal_at": None,
        }
        routing_scope = snapshot["routing_scope"]

        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            insert_ticket(active_connection, row={"id": ticket_id, **persisted})
            return StateChangeDraft(
                change_type="ticket.created",
                payload_json={
                    "ticket_id": str(ticket_id),
                    "category_id": str(request.category_id),
                    "category_version": persisted["category_version"],
                    "category_snapshot": snapshot,
                    "reporter_id": reporter_id,
                    "subject_id": request.subject_id,
                    "state": persisted["state"],
                    "priority": persisted["priority"],
                    "owner_id": None,
                    "resolution": None,
                    "client_ticket_id": request.client_ticket_id,
                    "terminal_at": None,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                },
            )

        try:
            result = mutate_entity(
                db=db,
                connection=connection,
                aggregate_type="ticket",
                aggregate_id=str(ticket_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface="api:/api/v1/tickets",
                ),
                action_type="ticket.create",
                action_payload={
                    "category_id": str(request.category_id),
                    "reporter_id": reporter_id,
                    "subject_id": request.subject_id,
                    "priority": request.priority or DEFAULT_TICKET_PRIORITY,
                    "client_ticket_id": request.client_ticket_id,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                },
                payload_allowlist=TICKET_CREATE_PAYLOAD_ALLOWLIST,
                mutate_projection=mutate_projection,
                scope_kind=routing_scope["scope_kind"],
                scope_id=routing_scope.get("scope_id"),
            )
        except errors.UniqueViolation as error:
            if request.client_ticket_id is None:
                raise
            with db.connection() as recovery_connection:
                existing = get_ticket_by_category_client_ticket_id(
                    recovery_connection,
                    category_id=request.category_id,
                    client_ticket_id=request.client_ticket_id,
                )
                if existing is None:
                    raise
                existing_read = _ticket_from_row(existing)
                initial_message = _load_duplicate_initial_message(
                    recovery_connection,
                    ticket_id=existing_read.id,
                )
            raise DuplicateTicketCreateError(existing_read, initial_message) from error

        initial_message, _created = append_ticket_message(
            db,
            ticket_id=ticket_id,
            request=request.initial_message,
            connection=connection,
        )
        ticket_read = _ticket_from_row(_fetch_ticket_row(connection, ticket_id))
    return TicketCreateRead(ticket=ticket_read, initial_message=initial_message), result


def read_ticket(
    db: PostgresDatabase,
    ticket_id: UUID,
) -> tuple[TicketRead, str]:
    with db.connection() as connection:
        read = _ticket_from_row(_fetch_ticket_row(connection, ticket_id))
    return read, f'"{read.version}"'


def transition_ticket(
    db: PostgresDatabase,
    ticket_id: UUID,
    expected_version: int,
    request: TicketTransitionRequest,
    actor: ActorIdentity,
) -> tuple[TicketRead, MutationResult]:
    transition_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        ticket_row = get_ticket_for_update(connection, ticket_id)
        if ticket_row is None:
            raise TicketNotFoundError(ticket_id)
        validated = validate_transition(ticket_row, request)
        aggregate_seq = expected_version + 1
        insert_ticket_transition(
            connection,
            row={
                "id": transition_id,
                "ticket_id": ticket_id,
                "aggregate_seq": aggregate_seq,
                "action": request.action,
                "from_state": ticket_row["state"],
                "to_state": validated["next_state"],
                "actor_kind": actor.actor_kind,
                "actor_id": actor.actor_id,
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
                "from_owner_id": ticket_row["owner_id"],
                "to_owner_id": validated["next_owner_id"],
                "from_priority": ticket_row["priority"],
                "to_priority": validated["next_priority"],
                "reason": validated["reason"],
                "resolution": validated["resolution"],
            },
        )
        update_ticket(
            connection,
            ticket_id=ticket_id,
            patch_row={
                "state": validated["next_state"],
                "priority": validated["next_priority"],
                "owner_id": validated["next_owner_id"],
                "resolution": validated["resolution"],
                "terminal_at": validated["next_terminal_at"],
            },
        )
        return StateChangeDraft(
            change_type="ticket.transitioned",
            payload_json={
                "ticket_id": str(ticket_id),
                "ticket_transition_id": str(transition_id),
                "action": request.action,
                "from_state": ticket_row["state"],
                "to_state": validated["next_state"],
                "reason": validated["reason"],
                "resolution": validated["resolution"],
                "owner_id": validated["next_owner_id"],
                "priority": validated["next_priority"],
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
            },
            diff_json=_build_transition_diff(ticket_row, validated),
        )

    with db.connection() as connection:
        current = _fetch_ticket_row(connection, ticket_id)
    routing_scope = current["category_snapshot"]["routing_scope"]
    result = mutate_entity(
        db=db,
        aggregate_type="ticket",
        aggregate_id=str(ticket_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/tickets/{ticket_id}/transitions",
        ),
        action_type="ticket.transition",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=TICKET_TRANSITION_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=routing_scope["scope_kind"],
        scope_id=routing_scope.get("scope_id"),
    )
    with db.connection() as connection:
        read = _ticket_from_row(_fetch_ticket_row(connection, ticket_id))
    return read, result
