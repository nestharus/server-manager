from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.authority import (
    AuthorityDecision,
    AuthorityGrantRead,
    AuthorityRequirement,
    GrantAlreadyRevokedError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.authority import fetch_active_grants_for, insert_grant, update_revoked_at
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity


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
    db: PostgresDatabase,
    grant_id: UUID,
) -> dict[str, Any]:
    with db.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT g.id, g.grantee_id, g.scope_kind, g.scope_id, g.permissions,
                   g.expires_at, g.revoked_at, g.predecessor_grant_id,
                   h.current_seq
            FROM authority_grants AS g
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'authority_grant'
             AND h.aggregate_id = g.id::text
            WHERE g.id = %s
            """,
            (grant_id,),
        ).fetchone()
    if row is None:
        raise LookupError(f"authority grant {grant_id} was not found")
    return row


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
) -> MutationResult:
    grant_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_grant(
            connection,
            grant_row={
                "id": grant_id,
                "grantee_id": grantee_id,
                "scope_kind": scope_kind,
                "scope_id": scope_id,
                "permissions": permissions,
                "expires_at": expires_at,
                "revoked_at": None,
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
                "predecessor_grant_id": None if predecessor_grant_id is None else str(predecessor_grant_id),
            },
        )

    return mutate_entity(
        db=db,
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


def revoke_authority(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    actor: tuple[str, str],
) -> MutationResult:
    row = _fetch_grant_row(db, grant_id)
    revoked_at = current_time()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        updated = update_revoked_at(connection, grant_id=grant_id, revoked_at=revoked_at)
        if updated != 1:
            raise GrantAlreadyRevokedError(grant_id)
        return StateChangeDraft(
            change_type="authority_grant.revoked",
            payload_json={"grant_id": str(grant_id), "revoked_at": revoked_at.isoformat()},
        )

    return mutate_entity(
        db=db,
        aggregate_type="authority_grant",
        aggregate_id=str(grant_id),
        request=_make_request(
            expected_version=int(row["current_seq"]),
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


def evaluate(
    requirement: AuthorityRequirement,
    grants: list[AuthorityGrantRead],
    *,
    at: datetime,
) -> AuthorityDecision:
    for grant in grants:
        if grant.revoked_at is not None and grant.revoked_at <= at:
            continue
        if grant.expires_at is not None and grant.expires_at <= at:
            continue
        if grant.scope_kind != requirement.scope_kind:
            continue
        if grant.scope_id is not None and grant.scope_id != requirement.scope_id:
            continue
        if requirement.permission not in grant.permissions:
            continue
        return AuthorityDecision(allowed=True)
    return AuthorityDecision(allowed=False)


def list_active_grants(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    at: datetime,
) -> list[AuthorityGrantRead]:
    with db.connection() as connection:
        rows = fetch_active_grants_for(connection, grantee_id=grantee_id, at=at)
    return [
        AuthorityGrantRead(
            id=row["id"],
            grantee_id=row["grantee_id"],
            scope_kind=row["scope_kind"],
            scope_id=row["scope_id"],
            permissions=frozenset(row["permissions"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            predecessor_grant_id=row["predecessor_grant_id"],
        )
        for row in rows
    ]
