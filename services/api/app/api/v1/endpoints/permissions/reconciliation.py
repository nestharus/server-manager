from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    PermissionReconciliationRunCreate,
    PermissionReconciliationRunRead,
    ReconciliationSnapshotRequest,
)
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permission_reconciliation import PermissionReconciliationService

from ._shared import (
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
@inject
def create_run_endpoint(
    body: PermissionReconciliationRunCreate,
    response: Response,
    service: PermissionReconciliationService = Depends(
        Provide[ApiContainer.services.permission_reconciliation]
    ),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    try:
        require_scoped(
            actor, body.scope_kind, body.scope_id,
            "permission_reconciliation_run.write",
            db=db,
        )
        read, result = service.create_reconciliation_run(request=body, actor=actor)
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.post(
    "/runs/{run_id}/snapshots",
    response_model=PermissionReconciliationRunRead,
)
@inject
def submit_snapshot_endpoint(
    run_id: UUID,
    body: ReconciliationSnapshotRequest,
    response: Response,
    service: PermissionReconciliationService = Depends(
        Provide[ApiContainer.services.permission_reconciliation]
    ),
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    try:
        existing = service.read_reconciliation_run(run_id)
        require_scoped(
            actor, existing.scope_kind, existing.scope_id,
            "permission_reconciliation_run.write",
            db=db,
        )
        read, result = service.submit_reconciliation_snapshot(
            run_id=run_id, entries=list(body.entries), actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read
