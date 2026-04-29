from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.authority import (
    AuthorityDecisionRead,
    AuthorityGrantTransferRequest,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityRequirement,
    DepartingRoleEntry,
    DenialReason,
    DuplicateActiveGrantError,
    GrantAlreadyTransferredError,
    GrantAlreadyRevokedError,
    InvalidHolderIdError,
    PendingApplicationRef,
    PendingTicketRef,
    SUCCESSION_TRANSFER_REVOCATION_REASON,
    SuccessionPlanRead,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.applications import list_open_applications_for_owner_ids
from app.repositories.authority import (
    fetch_grants_by_ids,
    fetch_grant,
    find_active_duplicate_grant_for_update,
    find_successor_grant,
    insert_grant,
    list_active_grants_for_grantee_ids,
    list_grants,
    update_revoked_with_reason,
)
from app.repositories.chapter_roles import list_succession_triggering_roles
from app.repositories.db import PostgresDatabase
from app.repositories.members import fetch_member_by_discord_id, fetch_member_by_id
from app.repositories.mutations import get_head_for_update
from app.repositories.roster import list_latest_role_holders
from app.repositories.tickets import list_open_tickets_for_owner_ids
from app.services.members import is_synthetic_member
from app.services.mutations import _format_etag, mutate_entity

OPEN_APPLICATION_STATES = frozenset(
    {
        "submitted",
        "queued",
        "claimed",
        "in_review",
        "interview",
        "waitlisted",
    }
)


def current_time() -> datetime:
    return datetime.now(UTC)


def _make_request(
    *,
    expected_version: int,
    actor: tuple[str, str],
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor[0],
        actor_id=actor[1],
        reason_text=None,
        request_surface=request_surface,
    )


def _fetch_grant_row(
    connection: Connection[Any],
    grant_id: UUID,
) -> dict[str, Any]:
    row = fetch_grant(connection, grant_id=grant_id)
    if row is None:
        raise LookupError(f"authority grant {grant_id} was not found")
    return row


def _row_to_read(row: dict[str, Any]) -> AuthorityGrantRead:
    return AuthorityGrantRead(
        id=row["id"],
        grantee_id=row["grantee_id"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        permissions=frozenset(row["permissions"]),
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        revoked_by=row.get("revoked_by"),
        revocation_reason=row.get("revocation_reason"),
        predecessor_grant_id=row["predecessor_grant_id"],
    )


def _find_active_duplicate_grant(
    connection: Connection[Any],
    *,
    grantee_id: str,
    scope_kind: str,
    scope_id: str | None,
    permissions: frozenset[str],
) -> AuthorityGrantRead | None:
    row = find_active_duplicate_grant_for_update(
        connection,
        grantee_id=grantee_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        permissions=permissions,
        at=current_time(),
    )
    if row is None:
        return None
    return _row_to_read(row)


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
    connection: Connection[Any],
    member_id: str,
    *,
    synthetic_policy: Literal["allow", "omit", "reject"] = "allow",
) -> tuple[set[str], set[UUID]]:
    canonical = _normalize_holder_id(member_id, field_name="holder_id")
    text_aliases = {canonical}
    uuid_aliases: set[UUID] = set()

    try:
        member_uuid = UUID(canonical)
    except ValueError:
        member_row = fetch_member_by_discord_id(connection, canonical)
        if member_row is not None:
            uuid_aliases.add(member_row["id"])
            text_aliases.add(str(member_row["id"]))
    else:
        uuid_aliases.add(member_uuid)
        member_row = fetch_member_by_id(connection, member_uuid)
        if member_row is not None:
            if is_synthetic_member(member_row["discord_user_id"]):
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
    connection: Connection[Any],
    member_ids: list[str],
    *,
    synthetic_policy: Literal["allow", "omit", "reject"] = "allow",
) -> tuple[list[str], list[UUID]]:
    text_aliases: set[str] = set()
    uuid_aliases: set[UUID] = set()
    for member_id in member_ids:
        member_text_aliases, member_uuid_aliases = _resolve_member_aliases(
            connection,
            member_id,
            synthetic_policy=synthetic_policy,
        )
        text_aliases.update(member_text_aliases)
        uuid_aliases.update(member_uuid_aliases)
    return sorted(text_aliases), sorted(uuid_aliases, key=str)


def grant_authority(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    scope_kind: str,
    scope_id: str | None,
    permissions: frozenset[str],
    expires_at: datetime | None,
    predecessor_grant_id: UUID | None,
    actor: tuple[str, str],
    connection: Connection[Any] | None = None,
) -> AuthorityGrantRead:
    grant_id = uuid4()
    if connection is None:
        with db.transaction() as transaction_connection:
            return grant_authority(
                db,
                grantee_id=grantee_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                permissions=permissions,
                expires_at=expires_at,
                predecessor_grant_id=predecessor_grant_id,
                actor=actor,
                connection=transaction_connection,
            )

    duplicate = _find_active_duplicate_grant(
        connection,
        grantee_id=grantee_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        permissions=permissions,
    )
    if duplicate is not None:
        raise DuplicateActiveGrantError(duplicate.id)

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        insert_grant(
            active_connection,
            grant_row={
                "id": grant_id,
                "grantee_id": grantee_id,
                "scope_kind": scope_kind,
                "scope_id": scope_id,
                "permissions": permissions,
                "expires_at": expires_at,
                "revoked_at": None,
                "revoked_by": None,
                "revocation_reason": None,
                "predecessor_grant_id": predecessor_grant_id,
            },
        )
        return StateChangeDraft(
            change_type="authority_grant.created",
            payload_json={
                "grant_id": str(grant_id),
                "grantee_id": grantee_id,
                "scope_kind": scope_kind,
                "scope_id": scope_id,
                "permissions": sorted(permissions),
                "expires_at": None if expires_at is None else expires_at.isoformat(),
                "predecessor_grant_id": (
                    None if predecessor_grant_id is None else str(predecessor_grant_id)
                ),
            },
        )

    mutate_entity(
        db=db,
        connection=connection,
        aggregate_type="authority_grant",
        aggregate_id=str(grant_id),
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="service:authority.grant",
        ),
        action_type="authority.grant",
        action_payload={},
        payload_allowlist=None,
        mutate_projection=mutate_projection,
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    return _row_to_read(_fetch_grant_row(connection, grant_id))


def revoke_authority(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    actor: tuple[str, str],
    revoked_by: str,
    reason: str,
    expected_version: int | None = None,
    connection: Connection[Any] | None = None,
) -> AuthorityGrantRead:
    if connection is None:
        with db.connection() as read_connection:
            row = _fetch_grant_row(read_connection, grant_id)
    else:
        row = _fetch_grant_row(connection, grant_id)
    revoked_at = current_time()

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        updated = update_revoked_with_reason(
            active_connection,
            grant_id=grant_id,
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            revocation_reason=reason,
        )
        if updated != 1:
            raise GrantAlreadyRevokedError(grant_id)
        return StateChangeDraft(
            change_type="authority_grant.revoked",
            payload_json={
                "grant_id": str(grant_id),
                "revoked_at": revoked_at.isoformat(),
                "revoked_by": revoked_by,
                "revocation_reason": reason,
            },
        )

    mutate_entity(
        db=db,
        connection=connection,
        aggregate_type="authority_grant",
        aggregate_id=str(grant_id),
        request=_make_request(
            expected_version=(
                int(row["current_seq"]) if expected_version is None else expected_version
            ),
            actor=actor,
            request_surface="service:authority.revoke",
        ),
        action_type="authority.revoke",
        action_payload={},
        payload_allowlist=None,
        mutate_projection=mutate_projection,
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
    )
    if connection is None:
        read, _etag = get_authority_grant(db, grant_id=grant_id)
        return read
    return _row_to_read(_fetch_grant_row(connection, grant_id))


def evaluate(
    requirement: AuthorityRequirement,
    grants: list[AuthorityGrantRead],
    *,
    at: datetime,
) -> AuthorityDecisionRead:
    has_any_grant = False
    has_scope_match = False
    has_permission_match = False
    saw_expired = False
    saw_revoked = False

    for grant in grants:
        has_any_grant = True
        if grant.scope_kind != requirement.scope_kind:
            continue
        if grant.scope_id is not None and grant.scope_id != requirement.scope_id:
            continue
        has_scope_match = True
        if requirement.permission not in grant.permissions:
            continue
        has_permission_match = True
        if grant.expires_at is not None and grant.expires_at <= at:
            saw_expired = True
            continue
        if grant.revoked_at is not None:
            saw_revoked = True
            continue
        return AuthorityDecisionRead(
            allowed=True,
            grant_id=grant.id,
            denial_reason=None,
            override_used=False,
        )

    denial_reason: DenialReason
    if not has_any_grant:
        denial_reason = "no_matching_grant"
    elif not has_scope_match:
        denial_reason = "scope_mismatch"
    elif not has_permission_match:
        denial_reason = "permission_missing"
    elif saw_expired:
        denial_reason = "grant_expired"
    else:
        denial_reason = "grant_revoked"

    return AuthorityDecisionRead(
        allowed=False,
        grant_id=None,
        denial_reason=denial_reason,
        override_used=False,
    )


def _collect_actor_grant_aliases(
    connection: Connection[Any],
    actor_id: str,
) -> list[str]:
    """Return every grantee_id alias an actor's grants could be stored under.

    Actors authenticate with either a member UUID, a Discord numeric ID, or a
    service/admin handle that does not correspond to a member row. Grants may
    have been written under any alias, so we merge all of them before
    evaluating permissions.
    """
    try:
        text_aliases, _ = _collect_member_aliases(connection, [actor_id])
    except InvalidHolderIdError:
        return [actor_id]
    if actor_id in text_aliases:
        return list(text_aliases)
    return [actor_id, *text_aliases]


def _require_scoped_authority(
    permission: str,
    *,
    scope_kind: str,
    scope_id: str | None,
    actor: ActorIdentity,
    db: PostgresDatabase,
) -> None:
    with db.connection() as connection:
        aliases = _collect_actor_grant_aliases(connection, actor.actor_id)
        seen_ids: set[UUID] = set()
        grants: list[AuthorityGrantRead] = []
        for alias in aliases:
            for row in list_grants(
                connection,
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
            permission=permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise PermissionError("authority requirement denied")


def list_authority_grants(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    include_revoked: bool = False,
    limit: int = 50,
    after_id: UUID | None = None,
) -> AuthorityGrantListRead:
    with db.connection() as connection:
        rows = list_grants(
            connection,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            include_revoked=include_revoked,
            limit=limit + 1,
            after_id=after_id,
        )
    items = [_row_to_read(row) for row in rows[:limit]]
    next_cursor = items[-1].id if len(rows) > limit and items else None
    return AuthorityGrantListRead(items=items, next_cursor=next_cursor)


def get_authority_grant(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
) -> tuple[AuthorityGrantRead, str]:
    with db.connection() as connection:
        row = _fetch_grant_row(connection, grant_id)
    return _row_to_read(row), _format_etag(int(row["current_seq"]))


def compute_succession_plan(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    actor: ActorIdentity,
) -> SuccessionPlanRead:
    _require_scoped_authority(
        "succession_plan.read",
        scope_kind="chapter",
        scope_id=chapter_id,
        actor=actor,
        db=db,
    )

    with db.connection() as connection:
        roles = list_succession_triggering_roles(connection, chapter_id=chapter_id)
        holders = {
            row["role_id"]: row
            for row in list_latest_role_holders(
                connection,
                chapter_id=chapter_id,
                role_ids=[row["id"] for row in roles],
            )
        }

        departing_roles: list[DepartingRoleEntry] = []
        holder_ids: list[str] = []
        for role in roles:
            holder = holders.get(role["id"])
            holder_member_id: str | None = None
            departure_signal = "active"
            if holder is not None:
                holder_member_id = _normalize_holder_id(
                    holder["member_id"],
                    field_name="holder_id",
                )
                holder_ids.append(holder_member_id)
                if holder["status"] == "removed":
                    departure_signal = "roster_removed"
            departing_roles.append(
                DepartingRoleEntry(
                    role_id=role["id"],
                    holder_member_id=holder_member_id,
                    triggers_succession=bool(role["triggers_succession"]),
                    departure_signal=departure_signal,  # type: ignore[arg-type]
                )
            )

        grant_aliases, application_owner_ids = _collect_member_aliases(
            connection,
            holder_ids,
            synthetic_policy="omit",
        )
        grant_rows = list_active_grants_for_grantee_ids(
            connection,
            grantee_ids=grant_aliases,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        application_rows = list_open_applications_for_owner_ids(
            connection,
            owner_ids=application_owner_ids,
            states=sorted(OPEN_APPLICATION_STATES),
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        ticket_rows = list_open_tickets_for_owner_ids(
            connection,
            owner_ids=grant_aliases,
            scope_kind="chapter",
            scope_id=chapter_id,
        )

    return SuccessionPlanRead(
        chapter_id=chapter_id,
        generated_at=current_time(),
        departing_roles=departing_roles,
        affected_grants=[_row_to_read(row) for row in grant_rows],
        pending_applications=[
            PendingApplicationRef(
                application_id=row["id"],
                owner_id=str(row["owner_id"]),
                state=str(row["state"]),
            )
            for row in application_rows
        ],
        pending_tickets=[
            PendingTicketRef(
                ticket_id=row["id"],
                owner_id=str(row["owner_id"]),
                state=str(row["state"]),
            )
            for row in ticket_rows
        ],
        successor_designated=False,
        successor_member_id=None,
    )


def transfer_authority_grant(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    expected_version: int,
    request: AuthorityGrantTransferRequest,
    actor: ActorIdentity,
) -> tuple[AuthorityGrantRead, MutationResult, bool]:
    successor_id = _normalize_holder_id(
        request.successor_id,
        field_name="successor_id",
    )
    _normalize_nonblank_text(request.reason, field_name="reason")

    with db.connection() as connection:
        predecessor = _fetch_grant_row(connection, grant_id)

    _require_scoped_authority(
        "authority_grant.transfer",
        scope_kind=predecessor["scope_kind"],
        scope_id=predecessor["scope_id"],
        actor=actor,
        db=db,
    )

    with db.transaction() as connection:
        get_head_for_update(
            connection,
            aggregate_type="authority_grant",
            aggregate_id=str(grant_id),
        )
        existing_successor = find_successor_grant(
            connection,
            predecessor_grant_id=grant_id,
        )
        if existing_successor is not None:
            if existing_successor["grantee_id"] == successor_id:
                successor_row = _fetch_grant_row(
                    connection, existing_successor["id"]
                )
                successor_version = int(successor_row["current_seq"])
                return (
                    _row_to_read(successor_row),
                    MutationResult(
                        version=successor_version,
                        etag=_format_etag(successor_version),
                    ),
                    False,
                )
            raise GrantAlreadyTransferredError(existing_successor["id"])
        if predecessor["revoked_at"] is not None:
            raise GrantAlreadyRevokedError(grant_id)

        successor = grant_authority(
            db,
            grantee_id=successor_id,
            scope_kind=predecessor["scope_kind"],
            scope_id=predecessor["scope_id"],
            permissions=frozenset(predecessor["permissions"]),
            expires_at=predecessor["expires_at"],
            predecessor_grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            connection=connection,
        )
        revoke_authority(
            db,
            grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            revoked_by=actor.actor_id,
            reason=SUCCESSION_TRANSFER_REVOCATION_REASON,
            expected_version=expected_version,
            connection=connection,
        )
        successor_row = _fetch_grant_row(connection, successor.id)
        successor_version = int(successor_row["current_seq"])
        return (
            successor,
            MutationResult(
                version=successor_version,
                etag=_format_etag(successor_version),
            ),
            True,
        )


def list_grants_for_grantee(
    db: PostgresDatabase,
    *,
    grantee_id: str,
) -> list[AuthorityGrantRead]:
    with db.connection() as connection:
        rows = list_grants(
            connection,
            grantee_id=grantee_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
    return [_row_to_read(row) for row in rows]


def get_authority_grants_by_ids(
    db: PostgresDatabase,
    *,
    grant_ids: list[UUID],
) -> list[AuthorityGrantRead]:
    with db.connection() as connection:
        rows = fetch_grants_by_ids(connection, grant_ids=grant_ids)
    return [_row_to_read(row) for row in rows]
