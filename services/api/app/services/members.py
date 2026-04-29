from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
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
    _insert_member_on_discord_conflict_do_nothing,
    _update_member_status,
    fetch_member_by_discord_id,
    fetch_member_by_id,
)
from app.core.context import get_current_audit_context, use_audit_context
from app.services.applicant_discord_auth import DISCORD_SNOWFLAKE_RE
from app.services.mutations import mutate_entity


VALID_TRANSITIONS = {
    ("active", "suspended"),
    ("suspended", "active"),
    ("active", "departed"),
    ("suspended", "departed"),
    ("departed", "active"),
}

APPLICANT_RECEIPT_MEMBER_ACTOR = ActorIdentity(
    actor_kind="service",
    actor_id="applicant-receipt",
)


class DiscordMemberRaceLost(Exception):
    pass


class NonDiscordMemberError(ValueError):
    pass


def is_synthetic_member(member: object) -> bool:
    if isinstance(member, Mapping):
        kind = member.get("kind")
    else:
        kind = getattr(member, "kind", None)
    return kind == "public_intake"


def _generated_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


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
        kind=row["kind"],
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


def _require_real_discord_member(row: dict[str, Any]) -> MemberRead:
    if row["kind"] != "discord":
        raise NonDiscordMemberError(
            "discord_user_id is already bound to a non-discord member row",
        )
    return _member_from_row(row)


async def resolve_or_create_real_discord_member(
    db: PostgresDatabase,
    *,
    discord_user_id: str,
    originating_actor: ActorIdentity | None = None,
    request_surface: str | None = None,
) -> MemberRead:
    if not DISCORD_SNOWFLAKE_RE.match(discord_user_id):
        raise ValueError("invalid Discord snowflake")
    resolved_actor = originating_actor or APPLICANT_RECEIPT_MEMBER_ACTOR
    resolved_surface = request_surface or "api:/api/v1/public/applications"

    def resolve_or_create() -> MemberRead:
        with db.connection() as connection:
            existing = fetch_member_by_discord_id(connection, discord_user_id)
        if existing is not None:
            return _require_real_discord_member(existing)

        member_id = uuid4()
        joined_at = datetime.now(UTC)
        action_payload = {
            "discord_user_id": discord_user_id,
            "joined_at": joined_at.isoformat(),
            "originating_actor_kind": resolved_actor.actor_kind,
            "originating_actor_id": resolved_actor.actor_id,
        }

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            inserted = _insert_member_on_discord_conflict_do_nothing(
                connection,
                row={
                    "id": member_id,
                    "discord_user_id": discord_user_id,
                    "joined_at": joined_at,
                    "status": "active",
                },
            )
            if not inserted:
                raise DiscordMemberRaceLost()
            return StateChangeDraft(
                change_type="member.created",
                payload_json={
                    "member_id": str(member_id),
                    "discord_user_id": discord_user_id,
                    "joined_at": joined_at.isoformat(),
                    "status": "active",
                    "originating_actor_kind": resolved_actor.actor_kind,
                    "originating_actor_id": resolved_actor.actor_id,
                },
            )

        try:
            mutate_entity(
                db=db,
                aggregate_type="member",
                aggregate_id=str(member_id),
                request=_make_request(
                    expected_version=0,
                    actor=resolved_actor,
                    request_surface=resolved_surface,
                ),
                action_type="member.create",
                action_payload=action_payload,
                payload_allowlist=set(action_payload.keys()),
                mutate_projection=mutate_projection,
                scope_kind="global",
                scope_id=None,
            )
        except DiscordMemberRaceLost:
            with db.connection() as connection:
                existing = _fetch_member_row_by_discord_id(connection, discord_user_id)
            return _require_real_discord_member(existing)

        with db.connection() as connection:
            row = _fetch_member_row(connection, member_id)
        return _require_real_discord_member(row)

    if get_current_audit_context() is None:
        with use_audit_context(_generated_audit_context()):
            return resolve_or_create()
    return resolve_or_create()


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
        if is_synthetic_member(row):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={
                    "code": "member_status_synthetic_not_allowed",
                    "message": "Synthetic public-intake member status cannot be mutated.",
                },
            )
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
    "is_synthetic_member",
    "NonDiscordMemberError",
    "patch_member_status",
]
