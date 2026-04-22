from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import (
    AuthorityGrantCreate,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityGrantRevoke,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import (
    _collect_actor_grant_aliases,
    _require_scoped_authority,
    get_authority_grant,
    grant_authority,
    list_authority_grants,
    revoke_authority,
)

from ._shared import get_db, parse_if_match_strong, raise_known_authority_error, set_etag


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("", response_model=AuthorityGrantRead, status_code=HTTPStatus.CREATED)
def create_authority_grant(
    body: AuthorityGrantCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    try:
        _require_scoped_authority(
            "authority_grant.create",
            scope_kind=body.scope_kind,
            scope_id=body.scope_id,
            actor=actor,
            db=db,
        )
        created = grant_authority(
            db=db,
            grantee_id=body.grantee_id,
            scope_kind=body.scope_kind,
            scope_id=body.scope_id,
            permissions=body.permissions,
            expires_at=body.expires_at,
            predecessor_grant_id=body.predecessor_grant_id,
            actor=(actor.actor_kind, actor.actor_id),
        )
        _read, etag = get_authority_grant(db, grant_id=created.id)
    except Exception as error:
        raise_known_authority_error(error)
    set_etag(response, etag)
    return created


@router.get("", response_model=AuthorityGrantListRead)
def list_authority_grants_endpoint(
    grantee_id: str,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    include_revoked: bool = False,
    limit: int = 50,
    after_id: UUID | None = None,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantListRead:
    try:
        with db.connection() as connection:
            actor_aliases = set(
                _collect_actor_grant_aliases(connection, actor.actor_id)
            )
        if grantee_id not in actor_aliases:
            _require_scoped_authority(
                "authority_grant.read",
                scope_kind=scope_kind if scope_kind is not None else "global",
                scope_id=scope_id,
                actor=actor,
                db=db,
            )
        return list_authority_grants(
            db,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            include_revoked=include_revoked,
            limit=limit,
            after_id=after_id,
        )
    except Exception as error:
        raise_known_authority_error(error)


@router.post("/{grant_id}/revoke", response_model=AuthorityGrantRead)
def revoke_authority_grant(
    grant_id: UUID,
    body: AuthorityGrantRevoke,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    expected_version = parse_if_match_strong(request)
    try:
        grant, _etag = get_authority_grant(db, grant_id=grant_id)
        _require_scoped_authority(
            "authority_grant.revoke",
            scope_kind=grant.scope_kind,
            scope_id=grant.scope_id,
            actor=actor,
            db=db,
        )
        revoked = revoke_authority(
            db=db,
            grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            revoked_by=actor.actor_id,
            reason=body.reason,
            expected_version=expected_version,
        )
        _read, etag = get_authority_grant(db, grant_id=revoked.id)
    except Exception as error:
        raise_known_authority_error(error)
    set_etag(response, etag)
    return revoked
