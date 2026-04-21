from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.members import (
    InvalidMemberStatusTransitionError,
    MemberCreate,
    MemberNotFoundError,
    MemberRead,
    MemberStatusPatch,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.db import PostgresDatabase
from app.repositories.members import (
    _fetch_member_by_id_for_update,
    _insert_member,
    _update_member_status,
    fetch_member_by_discord_id,
    fetch_member_by_id,
)
from app.services.mutations import mutate_entity


VALID_TRANSITIONS = {
    ("active", "suspended"),
    ("suspended", "active"),
    ("active", "departed"),
    ("suspended", "departed"),
    ("departed", "active"),
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


def _member_from_row(row: dict[str, Any]) -> MemberRead:
    return MemberRead(
        id=row["id"],
        discord_user_id=row["discord_user_id"],
        joined_at=row["joined_at"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _fetch_member_row(connection: Connection[Any], member_id: UUID) -> dict[str, Any]:
    row = fetch_member_by_id(connection, member_id)
    if row is None:
        raise MemberNotFoundError(member_id=member_id)
    return row


def _fetch_member_row_by_discord_id(
    connection: Connection[Any],
    discord_user_id: str,
) -> dict[str, Any]:
    row = fetch_member_by_discord_id(connection, discord_user_id)
    if row is None:
        raise MemberNotFoundError(discord_user_id=discord_user_id)
    return row


def create_or_get_member(
    db: PostgresDatabase,
    request: MemberCreate,
    actor: ActorIdentity,
) -> tuple[MemberRead, MutationResult | None, bool]:
    with db.connection() as connection:
        existing = fetch_member_by_discord_id(connection, request.discord_user_id)
    if existing is not None:
        return _member_from_row(existing), None, False

    member_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        _insert_member(
            connection,
            row={
                "id": member_id,
                "discord_user_id": request.discord_user_id,
                "joined_at": request.joined_at,
                "status": "active",
            },
        )
        return StateChangeDraft(
            change_type="member.created",
            payload_json={
                "member_id": str(member_id),
                "discord_user_id": request.discord_user_id,
                "joined_at": request.joined_at.isoformat(),
                "status": "active",
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
            },
        )

    try:
        result = mutate_entity(
            db=db,
            aggregate_type="member",
            aggregate_id=str(member_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="api:/api/v1/members",
            ),
            action_type="member.create",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
            scope_kind="global",
            scope_id=None,
        )
    except errors.UniqueViolation:
        with db.connection() as connection:
            existing = _fetch_member_row_by_discord_id(
                connection,
                request.discord_user_id,
            )
        return _member_from_row(existing), None, False

    with db.connection() as connection:
        row = _fetch_member_row(connection, member_id)
    return _member_from_row(row), result, True


def get_member_by_id(
    db: PostgresDatabase,
    member_id: UUID,
) -> tuple[MemberRead, str]:
    with db.connection() as connection:
        read = _member_from_row(_fetch_member_row(connection, member_id))
    return read, f'"{read.version}"'


def get_member_by_discord_id(
    db: PostgresDatabase,
    discord_user_id: str,
) -> tuple[MemberRead, str]:
    with db.connection() as connection:
        read = _member_from_row(
            _fetch_member_row_by_discord_id(connection, discord_user_id)
        )
    return read, f'"{read.version}"'


def patch_member_status(
    db: PostgresDatabase,
    member_id: UUID,
    request: MemberStatusPatch,
    actor: ActorIdentity,
    expected_version: int,
) -> tuple[MemberRead, MutationResult]:
    with db.connection() as connection:
        _fetch_member_row(connection, member_id)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = _fetch_member_by_id_for_update(connection, member_id)
        if row is None:
            raise MemberNotFoundError(member_id=member_id)
        from_status = row["status"]
        to_status = request.status
        if from_status == to_status or (from_status, to_status) not in VALID_TRANSITIONS:
            raise InvalidMemberStatusTransitionError(from_status, to_status)

        _update_member_status(
            connection,
            member_id=member_id,
            status=to_status,
        )
        return StateChangeDraft(
            change_type="member.status_changed",
            payload_json={
                "member_id": str(member_id),
                "from_status": from_status,
                "to_status": to_status,
                "reason": request.reason,
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
            },
            diff_json={
                "status": {"old": from_status, "new": to_status},
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="member",
        aggregate_id=str(member_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/members/{member_id}/status",
            reason_text=request.reason,
        ),
        action_type="member.status.patch",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump(mode="json").keys()),
        mutate_projection=mutate_projection,
        scope_kind="global",
        scope_id=None,
    )
    with db.connection() as connection:
        read = _member_from_row(_fetch_member_row(connection, member_id))
    return read, result


__all__ = [
    "create_or_get_member",
    "get_member_by_discord_id",
    "get_member_by_id",
    "patch_member_status",
]
