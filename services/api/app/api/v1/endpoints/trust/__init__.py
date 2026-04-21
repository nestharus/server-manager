from __future__ import annotations

from fastapi import APIRouter

from . import profiles, recompute, signals


router = APIRouter()
router.include_router(profiles.router)
router.include_router(recompute.router)
router.include_router(signals.router)

