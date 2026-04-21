from __future__ import annotations

from fastapi import APIRouter

from .forms import router as form_routes
from .interviews import router as interview_routes
from .lifecycle import router as lifecycle_routes


router = APIRouter()
router.include_router(form_routes, tags=["application-forms"])
router.include_router(lifecycle_routes, tags=["applications"])
router.include_router(interview_routes, tags=["applications"])


__all__ = ["router"]
