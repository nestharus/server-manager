from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.chapters import archive, base, governance


router = APIRouter()
router.include_router(base.router)
router.include_router(governance.router)
router.include_router(archive.router)


__all__ = ["router"]
