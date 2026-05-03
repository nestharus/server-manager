from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.persistence import MigrationRevisionRead
from app.core.container import ApiContainer
from app.repositories.db import PostgresDatabase

router = APIRouter(prefix="/api/v1/system")


@router.get("/migrations/current", response_model=MigrationRevisionRead)
@inject
def current_migration_revision(
    database: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
) -> MigrationRevisionRead:
    return MigrationRevisionRead(revision=database.current_revision())
