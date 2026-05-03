from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.runtime import ServiceHealthRead
from app.core.container import ApiContainer
from app.core.settings import Settings


router = APIRouter(prefix="/api/v1/health")


@router.get("", response_model=ServiceHealthRead)
@inject
def healthcheck(
    settings: Settings = Depends(Provide[ApiContainer.core.settings]),
) -> ServiceHealthRead:
    return ServiceHealthRead(status="alive", version=settings.app_version)
