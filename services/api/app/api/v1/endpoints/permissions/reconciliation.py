from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    PermissionReconciliationRunCreate,
    PermissionReconciliationRunRead,
    ReconciliationSnapshotRequest,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permission_reconciliation import (
    create_reconciliation_run,
    read_reconciliation_run,
    submit_reconciliation_snapshot,
)

from ._shared import (
    get_db,
    raise_known_permission_error,
    require_scoped,
    set_etag,
)


router = APIRouter(prefix="/api/v1/permission-reconciliation")


@router.post(
    "/runs",
    response_model=PermissionReconciliationRunRead,
    status_code=HTTPStatus.CREATED,
)
def create_run_endpoint(
    body: PermissionReconciliationRunCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    try:
        require_scoped(
            actor, db, body.scope_kind, body.scope_id,
            "permission_reconciliation_run.write",
        )
        read, result = create_reconciliation_run(db, request=body, actor=actor)
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.post(
    "/runs/{run_id}/snapshots",
    response_model=PermissionReconciliationRunRead,
)
def submit_snapshot_endpoint(
    run_id: UUID,
    body: ReconciliationSnapshotRequest,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    try:
        existing = read_reconciliation_run(db, run_id)
        require_scoped(
            actor, db, existing.scope_kind, existing.scope_id,
            "permission_reconciliation_run.write",
        )
        read, result = submit_reconciliation_snapshot(
            db, run_id=run_id, entries=list(body.entries), actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read
