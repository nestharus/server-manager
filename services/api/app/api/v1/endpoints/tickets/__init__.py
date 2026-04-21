from __future__ import annotations

from fastapi import APIRouter

from . import categories

router = APIRouter()
router.include_router(categories.router)

__all__ = ["router"]
