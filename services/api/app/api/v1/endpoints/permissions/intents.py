from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    ChannelRolePermissionIntent,
    ChannelRolePermissionIntentCreate,
    GuildRolePermissionIntent,
    GuildRolePermissionIntentCreate,
    PermissionIntentKind,
    PermissionIntentScopeKind,
    PermissionIntentUpdate,
)
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permissions import PermissionsService

from ._shared import (
    parse_if_match_strong,
    raise_known_permission_error,
    require_scoped,
    set_etag,
)


PermissionIntentCreateBody = Annotated[
    GuildRolePermissionIntentCreate | ChannelRolePermissionIntentCreate,
    Field(discriminator="kind"),
]

PermissionIntentReadResponse = Annotated[
    GuildRolePermissionIntent | ChannelRolePermissionIntent,
    Field(discriminator="kind"),
]


router = APIRouter(prefix="/api/v1/permission-intents")


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=PermissionIntentReadResponse,
)
@inject
def create_intent_endpoint(
    body: PermissionIntentCreateBody,
    response: Response,
    service: PermissionsService = Depends(Provide[ApiContainer.services.permissions]),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> Any:
    try:
        require_scoped(
            actor, body.scope_kind, body.scope_id,
            "permission_intent.write",
            db=db,
        )
        read, result = service.create_permission_intent(body, actor=actor)
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.patch("/{intent_id}", response_model=PermissionIntentReadResponse)
@inject
def patch_intent_endpoint(
    intent_id: UUID,
    body: PermissionIntentUpdate,
    request: Request,
    response: Response,
    service: PermissionsService = Depends(Provide[ApiContainer.services.permissions]),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> Any:
    expected_version = parse_if_match_strong(request)
    try:
        current = service.read_permission_intent(intent_id)
        require_scoped(
            actor, current.scope_kind, current.scope_id,
            "permission_intent.write",
            db=db,
        )
        read, result = service.update_permission_intent(
            intent_id,
            expected_version=expected_version,
            patch=body.model_dump(mode="python", exclude_unset=True),
            actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.get("", response_model=list[PermissionIntentReadResponse])
@inject
def list_intents_endpoint(
    scope_kind: PermissionIntentScopeKind,
    scope_id: str | None = Query(default=None),
    role_id: str | None = Query(default=None),
    channel_id: str | None = Query(default=None),
    kind: PermissionIntentKind | None = Query(default=None),
    temporary: bool | None = Query(default=None),
    include_expired: bool = Query(default=False),
    service: PermissionsService = Depends(Provide[ApiContainer.services.permissions]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[Any]:
    try:
        return service.list_permission_intents(
            actor=actor,
            scope_kind=scope_kind,
            scope_id=scope_id,
            role_id=role_id,
            channel_id=channel_id,
            kind=kind,
            temporary=temporary,
            include_expired=include_expired,
        )
    except Exception as error:
        raise_known_permission_error(error)
