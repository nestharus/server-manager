from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.authority import (
    AuthorityDecisionRead,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityRequirement,
    DenialReason,
    DuplicateActiveGrantError,
    GrantAlreadyRevokedError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.authority import (
    fetch_grant,
    find_active_duplicate_grant_for_update,
    insert_grant,
    list_grants,
    update_revoked_with_reason,
)
from app.repositories.db import PostgresDatabase
from app.services.mutations import _format_etag, mutate_entity


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
) -> AuthorityGrantRead:
    grant_id = uuid4()
    with db.transaction() as connection:
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
) -> AuthorityGrantRead:
    with db.connection() as connection:
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
    read, _etag = get_authority_grant(db, grant_id=grant_id)
    return read


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
