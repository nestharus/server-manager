from __future__ import annotations

from contextlib import nullcontext
from http import HTTPStatus
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityRequirement, InvalidHolderIdError
from app.repositories.authority import AuthorityRepository
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.services.members import is_synthetic_member


def _normalize_nonblank_text(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _normalize_holder_id(value: str, *, field_name: str) -> str:
    holder_id = _normalize_nonblank_text(value, field_name=field_name)
    try:
        UUID(holder_id)
        return holder_id
    except ValueError:
        if holder_id.isdigit():
            return holder_id
    raise InvalidHolderIdError(f"{field_name} must be a UUID or Discord ID string")


def _resolve_member_aliases(
    *,
    members_repo: MembersRepository,
    connection: Connection[Any],
    member_id: str,
    synthetic_policy: Literal["allow", "omit", "reject"] = "allow",
) -> tuple[set[str], set[UUID]]:
    canonical = _normalize_holder_id(member_id, field_name="holder_id")
    text_aliases = {canonical}
    uuid_aliases: set[UUID] = set()

    try:
        member_uuid = UUID(canonical)
    except ValueError:
        member_row = members_repo._fetch_member_by_discord_id_on(connection, canonical)
        if member_row is not None:
            uuid_aliases.add(member_row["id"])
            text_aliases.add(str(member_row["id"]))
    else:
        uuid_aliases.add(member_uuid)
        member_row = members_repo._fetch_member_by_id_on(connection, member_uuid)
        if member_row is not None:
            if is_synthetic_member(member_row):
                if synthetic_policy == "omit":
                    return set(), set()
                if synthetic_policy == "reject":
                    raise HTTPException(
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "leadership_alias_synthetic_not_allowed",
                            "message": (
                                "Synthetic public-intake members cannot be leaders "
                                "or alias targets."
                            ),
                        },
                    )
            text_aliases.add(member_row["discord_user_id"])

    return text_aliases, uuid_aliases


def _collect_member_aliases(
    connection: Connection[Any] | None = None,
    member_ids: list[str] | None = None,
    *,
    members_repo: MembersRepository | None = None,
    db: PostgresDatabase | None = None,
    synthetic_policy: Literal["allow", "omit", "reject"] = "allow",
) -> tuple[list[str], list[UUID]]:
    if members_repo is None:
        if db is None:
            raise TypeError("members_repo or db is required")
        members_repo = MembersRepository(db)
    if connection is None or member_ids is None:
        raise TypeError("connection and member_ids are required")
    text_aliases: set[str] = set()
    uuid_aliases: set[UUID] = set()
    for member_id in member_ids:
        member_text_aliases, member_uuid_aliases = _resolve_member_aliases(
            members_repo=members_repo,
            connection=connection,
            member_id=member_id,
            synthetic_policy=synthetic_policy,
        )
        text_aliases.update(member_text_aliases)
        uuid_aliases.update(member_uuid_aliases)
    return sorted(text_aliases), sorted(uuid_aliases, key=str)


def _collect_actor_grant_aliases(
    *,
    members_repo: MembersRepository,
    connection: Connection[Any],
    actor_id: str,
) -> list[str]:
    try:
        text_aliases, _ = _collect_member_aliases(
            members_repo=members_repo,
            connection=connection,
            member_ids=[actor_id],
        )
    except InvalidHolderIdError:
        return [actor_id]
    if actor_id in text_aliases:
        return list(text_aliases)
    return [actor_id, *text_aliases]


def _require_scoped_authority(
    permission: str | None = None,
    *,
    authority_repo: AuthorityRepository | None = None,
    members_repo: MembersRepository | None = None,
    db: PostgresDatabase | None = None,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    actor: ActorIdentity,
    connection: Connection[Any] | None = None,
    action: str | None = None,
    target_scope: tuple[str, str | None] | None = None,
) -> None:
    from app.services.authority import current_time, evaluate, _row_to_read

    if authority_repo is None:
        if db is None:
            raise TypeError("authority_repo or db is required")
        authority_repo = AuthorityRepository(db)
    if members_repo is None:
        if db is None:
            raise TypeError("members_repo or db is required")
        members_repo = MembersRepository(db)
    resolved_permission = permission or action
    if target_scope is not None:
        scope_kind, scope_id = target_scope
    if resolved_permission is None or scope_kind is None:
        raise TypeError("permission/action and scope_kind/target_scope are required")

    connection_context = (
        nullcontext(connection)
        if connection is not None
        else authority_repo.db.connection()
    )
    with connection_context as active_connection:
        aliases = _collect_actor_grant_aliases(
            members_repo=members_repo,
            connection=active_connection,
            actor_id=actor.actor_id,
        )
        seen_ids: set[UUID] = set()
        grants = []
        for alias in aliases:
            for row in authority_repo._list_grants_on(
                active_connection,
                grantee_id=alias,
                include_revoked=True,
                limit=None,
                after_id=None,
            ):
                if row["id"] in seen_ids:
                    continue
                seen_ids.add(row["id"])
                grants.append(_row_to_read(row))
    decision = evaluate(
        requirement=AuthorityRequirement(
            scope_kind=scope_kind,  # type: ignore[arg-type]
            scope_id=scope_id,
            permission=resolved_permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise PermissionError("authority requirement denied")


__all__ = ["_collect_member_aliases", "_require_scoped_authority"]
