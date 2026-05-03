from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import (
    AuthorityGrantCreate,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityGrantRevoke,
)
from app.core.dependencies import get_current_actor
from app.core.container import ApiContainer
from app.services.authority import AuthorityService

from ._shared import parse_if_match_strong, raise_known_authority_error, set_etag


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("", response_model=AuthorityGrantRead, status_code=HTTPStatus.CREATED)
@inject
def create_authority_grant(
    body: AuthorityGrantCreate,
    response: Response,
    service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    try:
        service.require_scoped_authority(
            "authority_grant.create",
            scope_kind=body.scope_kind,
            scope_id=body.scope_id,
            actor=actor,
        )
        created = service.grant_authority(
            grantee_id=body.grantee_id,
            scope_kind=body.scope_kind,
            scope_id=body.scope_id,
            permissions=body.permissions,
            expires_at=body.expires_at,
            predecessor_grant_id=body.predecessor_grant_id,
            actor=(actor.actor_kind, actor.actor_id),
        )
        _read, etag = service.get_authority_grant(grant_id=created.id)
    except Exception as error:
        raise_known_authority_error(error)
    set_etag(response, etag)
    return created


@router.get("", response_model=AuthorityGrantListRead)
@inject
def list_authority_grants_endpoint(
    grantee_id: str,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    include_revoked: bool = False,
    limit: int = 50,
    after_id: UUID | None = None,
    service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantListRead:
    try:
        with service._authority_repo.db.connection() as connection:
            actor_aliases = set(
                service._collect_actor_grant_aliases_on(connection, actor.actor_id)
            )
        if grantee_id not in actor_aliases:
            service.require_scoped_authority(
                "authority_grant.read",
                scope_kind=scope_kind if scope_kind is not None else "global",
                scope_id=scope_id,
                actor=actor,
            )
        return service.list_authority_grants(
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
@inject
def revoke_authority_grant(
    grant_id: UUID,
    body: AuthorityGrantRevoke,
    request: Request,
    response: Response,
    service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    expected_version = parse_if_match_strong(request)
    try:
        grant, _etag = service.get_authority_grant(grant_id=grant_id)
        service.require_scoped_authority(
            "authority_grant.revoke",
            scope_kind=grant.scope_kind,
            scope_id=grant.scope_id,
            actor=actor,
        )
        revoked = service.revoke_authority(
            grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            revoked_by=actor.actor_id,
            reason=body.reason,
            expected_version=expected_version,
        )
        _read, etag = service.get_authority_grant(grant_id=revoked.id)
    except Exception as error:
        raise_known_authority_error(error)
    set_etag(response, etag)
    return revoked
