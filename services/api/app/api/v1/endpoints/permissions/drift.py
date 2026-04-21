from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    PermissionDriftRead,
    PermissionDriftResolutionRequest,
    PermissionDriftStatus,
    PermissionIntentScopeKind,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permissions import (
    list_permission_drift,
    read_permission_drift,
    resolve_permission_drift,
)

from ._shared import (
    get_db,
    parse_if_match_strong,
    raise_known_permission_error,
    require_scoped,
    set_etag,
)


router = APIRouter(prefix="/api/v1/permission-drift")


@router.get("", response_model=list[PermissionDriftRead])
def list_drift_endpoint(
    status: list[PermissionDriftStatus] | None = Query(default=None),
    scope_kind: PermissionIntentScopeKind | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    role_id: str | None = Query(default=None),
    reconciliation_run_id: UUID | None = Query(default=None),
    has_intent: bool | None = Query(default=None),
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[PermissionDriftRead]:
    try:
        require_scoped(
            actor, db,
            scope_kind or "global",
            scope_id,
            "permission_drift.read",
        )
        return list_permission_drift(
            db,
            actor=actor,
            scope_kind=scope_kind,
            scope_id=scope_id,
            status=list(status) if status else None,
            role_id=role_id,
            reconciliation_run_id=reconciliation_run_id,
            has_intent=has_intent,
        )
    except Exception as error:
        raise_known_permission_error(error)


@router.post("/{drift_id}/resolve", response_model=PermissionDriftRead)
def resolve_drift_endpoint(
    drift_id: UUID,
    body: PermissionDriftResolutionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionDriftRead:
    expected_version = parse_if_match_strong(request)
    try:
        current = read_permission_drift(db, drift_id)
        require_scoped(
            actor, db, current.scope_kind, current.scope_id,
            "permission_drift.write",
        )
        read, result = resolve_permission_drift(
            db,
            drift_id=drift_id,
            request=body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read
