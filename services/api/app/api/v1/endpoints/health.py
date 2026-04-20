from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.runtime import ServiceHealthRead


router = APIRouter(prefix="/api/v1/health")


@router.get("", response_model=ServiceHealthRead)
def healthcheck(request: Request) -> ServiceHealthRead:
    settings = request.app.state.settings
    return ServiceHealthRead(status="alive", version=settings.app_version)
