from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.public_chapters import PublicChapterListRead
from app.core.container import ApiContainer
from app.services.public_chapters import PublicChaptersService


router = APIRouter(prefix="/api/v1/public/chapters")
_public_chapters_service_provider = Provide[ApiContainer.services.public_chapters]
_public_chapters_service_provider.__name__ = "public_chapters_service"


@router.get("", response_model=PublicChapterListRead)
@inject
def list_public_chapters_endpoint(
    service: PublicChaptersService = Depends(
        _public_chapters_service_provider
    ),
) -> PublicChapterListRead:
    """Public, no auth — returns active chapters only. No identity headers consumed."""
    return service.list_public_chapters()


__all__ = ["router"]
