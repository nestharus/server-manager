"""V1 API router.

All v1 endpoints are mounted here. Each endpoint module lives in
app/api/v1/endpoints/.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import audit, authority, chapters, health, ready, system

router = APIRouter()
router.include_router(audit.router, tags=["audit"])
router.include_router(authority.router, tags=["authority"])
router.include_router(chapters.router, tags=["chapters"])
router.include_router(health.router, tags=["health"])
router.include_router(ready.router, tags=["ready"])
router.include_router(system.router, tags=["system"])
