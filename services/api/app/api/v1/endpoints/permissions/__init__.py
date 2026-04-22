from __future__ import annotations

from fastapi import APIRouter

from .drift import router as drift_router
from .intents import router as intents_router
from .reconciliation import router as reconciliation_router
from .temporary import router as temporary_router


router = APIRouter()
router.include_router(intents_router, tags=["permission-intents"])
router.include_router(temporary_router, tags=["permission-intents"])
router.include_router(drift_router, tags=["permission-drift"])
router.include_router(reconciliation_router, tags=["permission-reconciliation"])


__all__ = ["router"]
