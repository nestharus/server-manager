from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

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
    scope_kind: PermissionIntentScopeKind = Query(...),
    status: list[PermissionDriftStatus] | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    role_id: str | None = Query(default=None),
    reconciliation_run_id: UUID | None = Query(default=None),
    has_intent: bool | None = Query(default=None),
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[PermissionDriftRead]:
    if scope_kind == "chapter" and scope_id is None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "scope_id is required when scope_kind='chapter'",
            },
        )
    if scope_kind == "global" and scope_id is not None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "scope_id must be omitted when scope_kind='global'",
            },
        )
    try:
        require_scoped(
            actor, db, scope_kind, scope_id, "permission_drift.read",
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
