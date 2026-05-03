from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.roster import (
    InvalidRosterStatusTransitionError,
    RosterDuplicateCurrentEntryError,
    RosterEntryCreate,
    RosterEntryNotFoundError,
    RosterEntryRead,
    RosterEntryTransitionRequest,
    RosterRoleChapterMismatchError,
    RosterRoleNotFoundError,
    RosterSyncFailureRequest,
)
from app.contracts.scheduler import DeferredEffectCreate
from app.core.context import get_current_audit_context
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.members import MembersRepository
from app.repositories.roster import RosterRepository
from app.services.members import is_synthetic_member
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


VALID_TRANSITIONS = {
    ("active", "on_leave"),
    ("active", "under_review"),
    ("active", "removed"),
    ("on_leave", "active"),
    ("on_leave", "removed"),
    ("under_review", "active"),
    ("under_review", "removed"),
}


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
    reason_text: str | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=reason_text,
        request_surface=request_surface,
    )


def _entry_from_row(row: dict[str, Any]) -> RosterEntryRead:
    return RosterEntryRead(
        id=row["id"],
        chapter_id=row["chapter_id"],
        member_id=row["member_id"],
        role_id=row["role_id"],
        status=row["status"],
        removal_metadata=row["removal_metadata"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _fetch_entry_row(
    roster_repo: RosterRepository,
    connection: Connection[Any],
    entry_id: UUID,
) -> dict[str, Any]:
    row = roster_repo._fetch_roster_entry_on(connection, entry_id)
    if row is None:
        raise RosterEntryNotFoundError(entry_id)
    return row


def _validate_role(
    roster_repo: RosterRepository,
    connection: Connection[Any],
    *,
    chapter_id: str,
    role_id: UUID,
) -> None:
    role = roster_repo._fetch_chapter_role_for_update_or_validate_on(
        connection,
        role_id=role_id,
    )
    if role is None:
        raise RosterRoleNotFoundError(role_id)
    if role["chapter_id"] != chapter_id:
        raise RosterRoleChapterMismatchError(role_id, chapter_id)


def _verify_transition(
    *,
    current_status: str,
    new_status: str,
    current_role_id: UUID,
    new_role_id: UUID | None,
) -> None:
    if current_status == new_status:
        if new_role_id is None or new_role_id == current_role_id:
            raise InvalidRosterStatusTransitionError(current_status, new_status)
        return
    if (current_status, new_status) not in VALID_TRANSITIONS:
        raise InvalidRosterStatusTransitionError(current_status, new_status)


def _is_current_entry_unique_violation(error: errors.UniqueViolation) -> bool:
    constraint = getattr(error.diag, "constraint_name", None)
    return constraint == "uq_roster__chapter_member_active"


def _validate_roster_member(
    members_repo: MembersRepository,
    connection: Connection[Any],
    member_id: str,
) -> None:
    try:
        parsed_member_id = UUID(member_id)
    except ValueError:
        return

    member = members_repo._fetch_member_by_id_on(connection, parsed_member_id)
    if member is None:
        return
    if is_synthetic_member(member):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "roster_member_synthetic_not_allowed",
                "message": "Synthetic public-intake members cannot be added to rosters.",
            },
        )


def _enqueue_roster_sync_retry(
    deferred_effects_repo: DeferredEffectsRepository,
    connection: Connection[Any],
    *,
    roster_entry: dict[str, Any],
    request: RosterSyncFailureRequest,
) -> dict[str, Any]:
    ctx = get_current_audit_context()
    if ctx is None:
        raise RuntimeError("missing audit context for deferred effect enqueue")
    effect = DeferredEffectCreate(
        subsystem="roster_role_sync",
        effect_type="roster_sync_retry",
        idempotency_key=(
            f"roster_sync_retry:{roster_entry['id']}:{request.transition_id}"
        ),
        payload_json={
            "roster_entry_id": str(roster_entry["id"]),
            "chapter_id": roster_entry["chapter_id"],
            "member_id": roster_entry["member_id"],
            "member_discord_user_id": request.member_discord_user_id,
            "transition_id": str(request.transition_id),
            "desired_discord_role_ids": request.desired_discord_role_ids,
            "operation": request.operation,
            "failed_at_step": request.failed_at_step,
            "failure_reason": request.reason,
            "error_type": request.error_type,
            "originating_actor_kind": request.originating_actor_kind,
            "originating_actor_id": request.originating_actor_id,
        },
        consequence_level="consequential",
        correlation_id=ctx.correlation_id,
        causation_id=ctx.causation_id,
    )
    return deferred_effects_repo._enqueue_effect_on(
        connection,
        effect=effect,
        correlation_id=ctx.correlation_id,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )


class RosterService:
    def __init__(
        self,
        roster_repo: RosterRepository,
        members_repo: MembersRepository,
        deferred_effects_repo: DeferredEffectsRepository,
        mutations_callable,
    ) -> None:
        self._roster_repo = roster_repo
        self._members_repo = members_repo
        self._deferred_effects_repo = deferred_effects_repo
        self._mutations_callable = mutations_callable

    def create_roster_entry(
        self,
        request: RosterEntryCreate,
        actor: ActorIdentity,
    ) -> tuple[RosterEntryRead, MutationResult]:
        entry_id = uuid4()
        return self._create_roster_entry_on(
            None,
            entry_id=entry_id,
            request=request,
            actor=actor,
        )

    def _create_roster_entry_on(
        self,
        connection: Connection[Any] | None,
        *,
        entry_id: UUID,
        request: RosterEntryCreate,
        actor: ActorIdentity,
    ) -> tuple[RosterEntryRead, MutationResult]:
        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            _validate_role(
                self._roster_repo,
                active_connection,
                chapter_id=request.chapter_id,
                role_id=request.role_id,
            )
            _validate_roster_member(
                self._members_repo,
                active_connection,
                request.member_id,
            )
            self._roster_repo._insert_roster_entry_on(
                active_connection,
                row={
                    "id": entry_id,
                    "chapter_id": request.chapter_id,
                    "member_id": request.member_id,
                    "role_id": request.role_id,
                    "removal_metadata": {},
                },
            )
            return StateChangeDraft(
                change_type="roster_entry.created",
                payload_json={
                    "roster_entry_id": str(entry_id),
                    "chapter_id": request.chapter_id,
                    "member_id": request.member_id,
                    "role_id": str(request.role_id),
                    "status": "active",
                },
            )

        try:
            result = self._mutations_callable(
                connection=connection,
                aggregate_type="roster_entry",
                aggregate_id=str(entry_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface="api:/api/v1/roster-entries",
                ),
                action_type="roster_entry.create",
                action_payload=request.model_dump(mode="json"),
                payload_allowlist=set(request.model_dump(mode="json").keys()),
                mutate_projection=mutate_projection,
                scope_kind="chapter",
                scope_id=request.chapter_id,
            )
        except errors.UniqueViolation as error:
            if _is_current_entry_unique_violation(error):
                raise RosterDuplicateCurrentEntryError(
                    request.chapter_id,
                    request.member_id,
                ) from error
            raise

        if connection is None:
            with self._roster_repo.db.connection() as read_connection:
                read = _entry_from_row(
                    _fetch_entry_row(self._roster_repo, read_connection, entry_id)
                )
        else:
            read = _entry_from_row(
                _fetch_entry_row(self._roster_repo, connection, entry_id)
            )
        return read, result

    def get_roster_entry(self, entry_id: UUID) -> tuple[RosterEntryRead, str]:
        with self._roster_repo.db.connection() as connection:
            return self._get_roster_entry_on(connection, entry_id)

    def _get_roster_entry_on(
        self,
        connection: Connection[Any],
        entry_id: UUID,
    ) -> tuple[RosterEntryRead, str]:
        read = _entry_from_row(
            _fetch_entry_row(self._roster_repo, connection, entry_id)
        )
        return read, f'"{read.version}"'

    def transition_roster_entry(
        self,
        entry_id: UUID,
        request: RosterEntryTransitionRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[RosterEntryRead, MutationResult]:
        with self._roster_repo.db.connection() as read_connection:
            _fetch_entry_row(self._roster_repo, read_connection, entry_id)
        return self._transition_roster_entry_on(
            None,
            entry_id,
            request,
            actor,
            expected_version,
        )

    def _transition_roster_entry_on(
        self,
        connection: Connection[Any] | None,
        entry_id: UUID,
        request: RosterEntryTransitionRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[RosterEntryRead, MutationResult]:
        transition_id = uuid4()
        if connection is None:
            with self._roster_repo.db.connection() as read_connection:
                current = _fetch_entry_row(self._roster_repo, read_connection, entry_id)
        else:
            current = _fetch_entry_row(self._roster_repo, connection, entry_id)

        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            row = self._roster_repo._fetch_roster_entry_for_update_on(
                active_connection,
                entry_id,
            )
            if row is None:
                raise RosterEntryNotFoundError(entry_id)

            next_role_id = request.to_role_id or row["role_id"]
            _verify_transition(
                current_status=row["status"],
                new_status=request.to_status,
                current_role_id=row["role_id"],
                new_role_id=request.to_role_id,
            )
            if request.to_role_id is not None:
                _validate_role(
                    self._roster_repo,
                    active_connection,
                    chapter_id=row["chapter_id"],
                    role_id=request.to_role_id,
                )

            aggregate_seq = expected_version + 1
            self._roster_repo._insert_roster_transition_on(
                active_connection,
                row={
                    "id": transition_id,
                    "roster_entry_id": entry_id,
                    "chapter_id": row["chapter_id"],
                    "aggregate_seq": aggregate_seq,
                    "from_status": row["status"],
                    "to_status": request.to_status,
                    "from_role_id": row["role_id"],
                    "to_role_id": next_role_id,
                    "actor_kind": actor.actor_kind,
                    "actor_id": actor.actor_id,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                    "reason": request.reason,
                    "removal_metadata": request.removal_metadata,
                },
            )
            self._roster_repo._update_roster_entry_on(
                active_connection,
                entry_id=entry_id,
                status=request.to_status,
                role_id=next_role_id,
                removal_metadata=request.removal_metadata,
            )
            return StateChangeDraft(
                change_type="roster_entry.transitioned",
                payload_json={
                    "roster_transition_id": str(transition_id),
                    "roster_entry_id": str(entry_id),
                    "chapter_id": row["chapter_id"],
                    "member_id": row["member_id"],
                    "from_status": row["status"],
                    "to_status": request.to_status,
                    "from_role_id": str(row["role_id"]),
                    "to_role_id": str(next_role_id),
                    "reason": request.reason,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                    "removal_metadata": request.removal_metadata,
                },
                diff_json={
                    "status": {"old": row["status"], "new": request.to_status},
                    "role_id": {"old": str(row["role_id"]), "new": str(next_role_id)},
                },
            )

        result = self._mutations_callable(
            connection=connection,
            aggregate_type="roster_entry",
            aggregate_id=str(entry_id),
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/roster-entries/{entry_id}/transitions",
                reason_text=request.reason,
            ),
            action_type="roster_entry.transition",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
            scope_kind="chapter",
            scope_id=current["chapter_id"],
        )
        if connection is None:
            with self._roster_repo.db.connection() as read_connection:
                read = _entry_from_row(
                    _fetch_entry_row(self._roster_repo, read_connection, entry_id)
                )
        else:
            read = _entry_from_row(
                _fetch_entry_row(self._roster_repo, connection, entry_id)
            )
        return read, result

    def record_roster_sync_failure(
        self,
        entry_id: UUID,
        request: RosterSyncFailureRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[RosterEntryRead, MutationResult]:
        return self._record_roster_sync_failure_on(
            None,
            entry_id=entry_id,
            request=request,
            actor=actor,
            expected_version=expected_version,
        )

    def _record_roster_sync_failure_on(
        self,
        connection: Connection[Any] | None,
        *,
        entry_id: UUID,
        request: RosterSyncFailureRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[RosterEntryRead, MutationResult]:
        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            row = self._roster_repo._fetch_roster_entry_for_update_on(
                active_connection,
                entry_id,
            )
            if row is None:
                raise RosterEntryNotFoundError(entry_id)
            effect_row = _enqueue_roster_sync_retry(
                self._deferred_effects_repo,
                active_connection,
                roster_entry=row,
                request=request,
            )
            self._roster_repo._touch_roster_entry_on(
                active_connection, entry_id=entry_id
            )
            return StateChangeDraft(
                change_type="roster_entry.sync_failure_recorded",
                payload_json={
                    "roster_entry_id": str(entry_id),
                    "roster_transition_id": str(request.transition_id),
                    "deferred_effect_id": str(effect_row["id"]),
                    "deferred_effect_idempotency_key": effect_row["idempotency_key"],
                    "failure_reason": request.reason,
                    "operation": request.operation,
                    "failed_at_step": request.failed_at_step,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                },
            )

        result = self._mutations_callable(
            connection=connection,
            aggregate_type="roster_entry",
            aggregate_id=str(entry_id),
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/roster-entries/{entry_id}/sync-failure",
                reason_text=request.reason,
            ),
            action_type="roster_entry.sync_failure",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
            scope_kind="global",
            scope_id=None,
        )
        if connection is None:
            with self._roster_repo.db.connection() as read_connection:
                read = _entry_from_row(
                    _fetch_entry_row(self._roster_repo, read_connection, entry_id)
                )
        else:
            read = _entry_from_row(
                _fetch_entry_row(self._roster_repo, connection, entry_id)
            )
        return read, result


__all__ = [
    "RosterService",
]
