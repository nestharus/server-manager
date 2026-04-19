from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.persistence import MigrationRevisionRead

router = APIRouter(prefix="/api/v1/system")


@router.get("/migrations/current", response_model=MigrationRevisionRead)
def current_migration_revision(request: Request) -> MigrationRevisionRead:
    database = request.app.state.db
    return MigrationRevisionRead(revision=database.current_revision())
