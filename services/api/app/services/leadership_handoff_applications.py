from __future__ import annotations

from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationAlreadyClaimedError,
    ApplicationNotFoundError,
    ApplicationNotOwnerError,
    ApplicationTransitionRequest,
    InvalidApplicationTransitionError,
)
from app.contracts.authority import HandoffFailure, HandoffResult, LeadershipHandoffRequest
from app.contracts.mutations import StaleMutationError
from app.services.applications import ApplicationsService
from app.services._helpers.authority import (
    _collect_member_aliases,
    _require_scoped_authority,
)
from app.services.authority import (
    AuthorityService,
    OPEN_APPLICATION_STATES,
    _normalize_holder_id,
    _row_to_read,
)


def _failure_reason(error: Exception) -> str:
    if isinstance(error, (StaleMutationError, ApplicationAlreadyClaimedError)):
        return "occ_conflict"
    if isinstance(error, PermissionError):
        return "unauthorized"
    if isinstance(
        error,
        (
            ApplicationNotFoundError,
            ApplicationNotOwnerError,
            InvalidApplicationTransitionError,
            ValueError,
        ),
    ):
        return "invalid_state"
    raise error


class LeadershipHandoffApplicationsService:
    def __init__(
        self,
        applications_service: ApplicationsService,
        authority_service: AuthorityService,
    ) -> None:
        self._applications_service = applications_service
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
            _predecessor_aliases, predecessor_uuid_aliases = _collect_member_aliases(
                members_repo=members_repo,
                connection=connection,
                member_ids=[grant.grantee_id],
            )
            _successor_aliases, successor_uuid_aliases = _collect_member_aliases(
                members_repo=members_repo,
                connection=connection,
                member_ids=[successor_member_id],
            )
            if not successor_uuid_aliases:
                raise ValueError(
                    "successor_member_id must resolve to a member UUID for application handoff"
                )
            applications_repo = self._applications_service._applications_repo
            application_rows = applications_repo._list_open_applications_for_owner_ids_on(
                connection,
                owner_ids=sorted(
                    set(predecessor_uuid_aliases) | set(successor_uuid_aliases),
                    key=str,
                ),
                states=sorted(OPEN_APPLICATION_STATES),
                scope_kind=grant.scope_kind,
                scope_id=grant.scope_id,
            )

        transferred: list[UUID] = []
        already_owned: list[UUID] = []
        failed: list[HandoffFailure] = []
        successor_uuid = sorted(successor_uuid_aliases, key=str)[0]

        for row in application_rows:
            owner_id = row["owner_id"]
            if owner_id in successor_uuid_aliases:
                already_owned.append(row["id"])
                continue
            if owner_id not in predecessor_uuid_aliases:
                continue
            try:
                self._applications_service.transition_application(
                    application_id=row["id"],
                    expected_version=int(row["version"]),
                    request=ApplicationTransitionRequest(
                        action="reassign",
                        new_owner_id=successor_uuid,
                        originating_actor_kind=actor.actor_kind,
                        originating_actor_id=actor.actor_id,
                    ),
                    actor=actor,
                    request_surface=(
                        f"service:authority-grants/{grant_id}/handoff/applications"
                    ),
                    skip_authority_check=True,
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


__all__ = ["LeadershipHandoffApplicationsService"]
