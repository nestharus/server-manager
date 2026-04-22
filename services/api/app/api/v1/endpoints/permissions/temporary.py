from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    PermissionExpirySweepResult,
    PermissionIntentRenewalRequest,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permissions import (
    expire_temporary_permission_intents,
    read_permission_intent,
    renew_permission_intent,
)

from ._shared import (
    get_db,
    parse_if_match_strong,
    raise_known_permission_error,
    require_scoped,
    set_etag,
)
from .intents import PermissionIntentReadResponse


router = APIRouter(prefix="/api/v1/permission-intents")


@router.post("/{intent_id}/renew", response_model=PermissionIntentReadResponse)
def renew_intent_endpoint(
    intent_id: UUID,
    body: PermissionIntentRenewalRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> Any:
    expected_version = parse_if_match_strong(request)
    try:
        current = read_permission_intent(db, intent_id)
        require_scoped(
            actor,
            db,
            current.scope_kind,
            current.scope_id,
            "permission_intent.write",
        )
        read, result = renew_permission_intent(
            db,
            intent_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.post(
    "/expire/run",
    status_code=HTTPStatus.OK,
    response_model=PermissionExpirySweepResult,
)
def run_permission_expiry_endpoint(
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionExpirySweepResult:
    try:
        require_scoped(
            actor,
            db,
            "global",
            None,
            "permission_intent.write",
        )
        return expire_temporary_permission_intents(
            db,
            actor=actor,
            source="manual_trigger",
        )
    except Exception as error:
        raise_known_permission_error(error)
