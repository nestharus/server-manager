from __future__ import annotations

from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.authority import HandoffFailure, HandoffResult, LeadershipHandoffRequest
from app.contracts.mutations import StaleMutationError
from app.contracts.tickets import InvalidTicketTransitionError, TicketNotFoundError, TicketTransitionRequest
from app.repositories.db import PostgresDatabase
from app.repositories.tickets import list_open_tickets_for_owner_ids
from app.services.authority import (
    _collect_member_aliases,
    _normalize_holder_id,
    _require_scoped_authority,
    get_authority_grant,
)
from app.services.tickets import transition_ticket


def _failure_reason(error: Exception) -> str:
    if isinstance(error, StaleMutationError):
        return "occ_conflict"
    if isinstance(error, PermissionError):
        return "unauthorized"
    if isinstance(error, (InvalidTicketTransitionError, TicketNotFoundError, ValueError)):
        return "invalid_state"
    raise error


def execute_handoff(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    request: LeadershipHandoffRequest,
    actor: ActorIdentity,
) -> HandoffResult:
    grant, _etag = get_authority_grant(db, grant_id=grant_id)
    _require_scoped_authority(
        "leadership_handoff.execute",
        scope_kind=grant.scope_kind,
        scope_id=grant.scope_id,
        actor=actor,
        db=db,
    )
    successor_member_id = _normalize_holder_id(
        request.successor_member_id,
        field_name="successor_member_id",
    )

    with db.connection() as connection:
        predecessor_text_aliases, _predecessor_uuid_aliases = _collect_member_aliases(
            connection,
            [grant.grantee_id],
        )
        successor_text_aliases, _successor_uuid_aliases = _collect_member_aliases(
            connection,
            [successor_member_id],
        )
        ticket_rows = list_open_tickets_for_owner_ids(
            connection,
            owner_ids=sorted(set(predecessor_text_aliases) | set(successor_text_aliases)),
            scope_kind=grant.scope_kind,
            scope_id=grant.scope_id,
        )

    transferred: list[UUID] = []
    already_owned: list[UUID] = []
    failed: list[HandoffFailure] = []

    for row in ticket_rows:
        owner_id = str(row["owner_id"])
        if owner_id in successor_text_aliases:
            already_owned.append(row["id"])
            continue
        if owner_id not in predecessor_text_aliases:
            continue
        try:
            transition_ticket(
                db,
                ticket_id=row["id"],
                expected_version=int(row["version"]),
                request=TicketTransitionRequest(
                    action="reassign",
                    to_state=str(row["state"]),
                    new_owner_id=successor_member_id,
                    originating_actor_kind=actor.actor_kind,  # type: ignore[arg-type]
                    originating_actor_id=actor.actor_id,
                ),
                actor=actor,
            )
        except Exception as error:
            failed.append(
                HandoffFailure(
                    item_id=row["id"],
                    reason=_failure_reason(error),  # type: ignore[arg-type]
                    detail=str(error),
                )
            )
            continue
        transferred.append(row["id"])

    return HandoffResult(
        transferred=transferred,
        already_owned=already_owned,
        failed=failed,
    )
