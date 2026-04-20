from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.contracts.runtime import DependencyStatusRead, ServiceReadinessRead


router = APIRouter(prefix="/api/v1/ready")


def _database_status(request: Request) -> DependencyStatusRead:
    database = request.app.state.db
    try:
        with database.connection():
            pass
    except Exception as error:
        return DependencyStatusRead(
            name="database",
            status="not_ready",
            reason=str(error) or "database connection failed",
        )
    return DependencyStatusRead(name="database", status="ok")


def _migration_status(request: Request) -> DependencyStatusRead:
    database = request.app.state.db
    try:
        revision = database.current_revision()
    except Exception as error:
        return DependencyStatusRead(
            name="migrations",
            status="not_ready",
            reason=str(error) or "failed to read current revision",
        )
    if not revision.strip():
        return DependencyStatusRead(
            name="migrations",
            status="not_ready",
            reason="current migration revision is empty",
        )
    return DependencyStatusRead(name="migrations", status="ok")


def _scheduler_status(request: Request) -> DependencyStatusRead:
    scheduler_loop = request.app.state.scheduler_loop
    if scheduler_loop.is_running:
        return DependencyStatusRead(name="scheduler", status="ok")
    return DependencyStatusRead(
        name="scheduler",
        status="not_ready",
        reason="scheduler loop is not running",
    )


@router.get("", response_model=ServiceReadinessRead)
def readiness(request: Request) -> JSONResponse:
    dependencies = [
        _database_status(request),
        _migration_status(request),
        _scheduler_status(request),
    ]
    ready = all(dependency.status == "ok" for dependency in dependencies)
    payload = ServiceReadinessRead(
        status="ready" if ready else "not_ready",
        dependencies=dependencies,
    )
    return JSONResponse(
        status_code=200 if ready else 503,
        content=payload.model_dump(mode="json"),
    )
