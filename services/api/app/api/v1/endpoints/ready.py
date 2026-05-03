from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.contracts.runtime import DependencyStatusRead, ServiceReadinessRead
from app.core.container import ApiContainer
from app.repositories.db import PostgresDatabase
from app.services.scheduler import SchedulerService


router = APIRouter(prefix="/api/v1/ready")


def _database_status(database: PostgresDatabase) -> DependencyStatusRead:
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


def _migration_status(database: PostgresDatabase) -> DependencyStatusRead:
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


def _scheduler_status(scheduler_loop: SchedulerService) -> DependencyStatusRead:
    if scheduler_loop.is_running:
        return DependencyStatusRead(name="scheduler", status="ok")
    return DependencyStatusRead(
        name="scheduler",
        status="not_ready",
        reason="scheduler loop is not running",
    )


@router.get("", response_model=ServiceReadinessRead)
@inject
def readiness(
    database: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    scheduler_loop: SchedulerService = Depends(Provide[ApiContainer.tasks.scheduler_loop]),
) -> JSONResponse:
    dependencies = [
        _database_status(database),
        _migration_status(database),
        _scheduler_status(scheduler_loop),
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
