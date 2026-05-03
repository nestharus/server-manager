from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityDecisionRead, AuthorityRequirement
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.ticket_categories import (
    InvalidTicketSlaRulesError,
    InvalidTicketStateMachineError,
    TicketCategoryNotFoundError,
    TicketCategoryPatchEmptyError,
)
from app.contracts.ticket_messages import (
    TicketMessageAppendForbiddenError,
    TicketMessageVisibilityError,
)
from app.contracts.tickets import (
    DuplicateTicketCreateError,
    InvalidTicketTransitionError,
    TicketNotFoundError,
    TicketTransitionOwnerChangeForbiddenError,
    TicketTransitionPriorityChangeForbiddenError,
    TicketTransitionReasonRequiredError,
    TicketTransitionResolutionRequiredError,
)
from app.core.dependencies import get_current_actor
from app.repositories.authority import AuthorityRepository
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, _row_to_read

MIN_STRONG_ETAG_LENGTH = 3


def parse_if_match_strong(request: Request) -> int:
    if_match = request.headers.get("If-Match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail={"code": "if_match_required", "message": "If-Match header required"},
        )
    if (
        len(if_match) < MIN_STRONG_ETAG_LENGTH
        or not if_match.startswith('"')
        or not if_match.endswith('"')
    ):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        )
    try:
        return int(if_match[1:-1])
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        ) from error


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def service_actor_only(actor: ActorIdentity = Depends(get_current_actor)) -> ActorIdentity:
    if actor.actor_kind != "service":
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "service_actor_required",
                "message": "ticket command endpoints require a service actor",
            },
        )
    if actor.actor_id != "discord-ticket-bot":
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "discord_ticket_bot_required",
                "message": "ticket command endpoints require discord-ticket-bot",
            },
        )
    return actor


def require_authority_for_grantee(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> AuthorityDecisionRead:
    requirement = AuthorityRequirement(
        scope_kind=scope_kind,  # type: ignore[arg-type]
        scope_id=scope_id,
        permission=permission,
    )
    authority_repo = AuthorityRepository(db)
    grants = [
        _row_to_read(row)
        for row in authority_repo.list_grants(
            grantee_id=grantee_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
    ]
    decision = evaluate(requirement=requirement, grants=grants, at=current_time())
    if not decision.allowed:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "authority_decision_denied",
                "message": "authority requirement denied",
                "decision": decision.model_dump(mode="json"),
            },
        )
    return decision


def raise_known_ticket_error(error: Exception) -> None:
    if isinstance(error, (TicketCategoryNotFoundError, TicketNotFoundError, MissingAggregateError)):
        code = (
            "ticket_category_not_found"
            if isinstance(error, TicketCategoryNotFoundError)
            else "ticket_not_found"
        )
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": code, "message": str(error)},
        ) from error
    if isinstance(error, TicketCategoryPatchEmptyError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "ticket_category_patch_empty", "message": str(error)},
        ) from error
    if isinstance(error, InvalidTicketStateMachineError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_state_machine", "message": str(error)},
        ) from error
    if isinstance(error, InvalidTicketSlaRulesError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_sla_rules", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        code = (
            "stale_ticket_category_version"
            if error.aggregate_type == "ticket_category"
            else "stale_ticket_version"
        )
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": code,
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, DuplicateTicketCreateError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "duplicate_ticket_create",
                "ticket": error.ticket.model_dump(mode="json"),
                "initial_message": error.initial_message.model_dump(mode="json"),
            },
            headers={"etag": f'"{error.ticket.version}"'},
        ) from error
    if isinstance(error, InvalidTicketTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_ticket_transition",
                "message": str(error),
                "from_state": error.from_state,
                "action": error.action,
                "to_state": error.to_state,
            },
        ) from error
    if isinstance(error, TicketTransitionReasonRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "ticket_transition_reason_required",
                "message": str(error),
                "from_state": error.from_state,
                "action": error.action,
                "to_state": error.to_state,
            },
        ) from error
    if isinstance(error, TicketTransitionResolutionRequiredError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "ticket_transition_resolution_required",
                "message": str(error),
                "from_state": error.from_state,
                "action": error.action,
                "to_state": error.to_state,
            },
        ) from error
    if isinstance(
        error,
        (
            TicketTransitionOwnerChangeForbiddenError,
            TicketTransitionPriorityChangeForbiddenError,
        ),
    ):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "invalid_ticket_transition", "message": str(error)},
        ) from error
    if isinstance(error, TicketMessageVisibilityError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "ticket_message_visibility_error", "message": str(error)},
        ) from error
    if isinstance(error, TicketMessageAppendForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "ticket_message_append_forbidden", "message": str(error)},
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    raise error


def ticket_scope_from_ticket(ticket: Any) -> tuple[str, str | None]:
    routing_scope = ticket.category_snapshot.routing_scope
    return routing_scope.scope_kind, routing_scope.scope_id


def ticket_scope_from_snapshot(snapshot: dict[str, Any]) -> tuple[str, str | None]:
    routing_scope = snapshot["routing_scope"]
    return str(routing_scope["scope_kind"]), routing_scope.get("scope_id")


def parse_ticket_id(raw_value: str) -> UUID:
    return UUID(raw_value)
