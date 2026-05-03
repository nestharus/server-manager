from __future__ import annotations

from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.authority import HandoffFailure, HandoffResult, LeadershipHandoffRequest
from app.contracts.mutations import StaleMutationError
from app.contracts.tickets import InvalidTicketTransitionError, TicketNotFoundError, TicketTransitionRequest
from app.services._helpers.authority import (
    _collect_member_aliases,
    _require_scoped_authority,
)
from app.services.authority import (
    AuthorityService,
    _normalize_holder_id,
    _row_to_read,
)
from app.services.tickets import TicketsService


def _failure_reason(error: Exception) -> str:
    if isinstance(error, StaleMutationError):
        return "occ_conflict"
    if isinstance(error, PermissionError):
        return "unauthorized"
    if isinstance(error, (InvalidTicketTransitionError, TicketNotFoundError, ValueError)):
        return "invalid_state"
    raise error


class LeadershipHandoffTicketsService:
    def __init__(
        self,
        tickets_service: TicketsService,
        authority_service: AuthorityService,
    ) -> None:
        self._tickets_service = tickets_service
        self._authority_service = authority_service

    def execute_handoff(
        self,
        *,
        grant_id: UUID,
        request: LeadershipHandoffRequest,
        actor: ActorIdentity,
    ) -> HandoffResult:
        authority_repo = self._authority_service._authority_repo
        members_repo = self._authority_service._members_repo
        with authority_repo.db.connection() as connection:
            grant_row = self._authority_service._fetch_grant_row_on(connection, grant_id)
            grant = _row_to_read(grant_row)
            _require_scoped_authority(
                authority_repo=authority_repo,
                members_repo=members_repo,
                permission="leadership_handoff.execute",
                scope_kind=grant.scope_kind,
                scope_id=grant.scope_id,
                actor=actor,
                connection=connection,
            )
            successor_member_id = _normalize_holder_id(
                request.successor_member_id,
                field_name="successor_member_id",
            )
            predecessor_text_aliases, _predecessor_uuid_aliases = _collect_member_aliases(
                members_repo=members_repo,
                connection=connection,
                member_ids=[grant.grantee_id],
            )
            successor_text_aliases, _successor_uuid_aliases = _collect_member_aliases(
                members_repo=members_repo,
                connection=connection,
                member_ids=[successor_member_id],
            )
            ticket_rows = self._tickets_service.tickets_repo._list_open_tickets_for_owner_ids_on(
                connection,
                owner_ids=sorted(
                    set(predecessor_text_aliases) | set(successor_text_aliases)
                ),
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
                self._tickets_service.transition_ticket(
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


__all__ = ["LeadershipHandoffTicketsService"]
