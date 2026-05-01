from __future__ import annotations

from fastapi import APIRouter

from .forms import router as form_routes
from .interviews import router as interview_routes
from .lifecycle import router as lifecycle_routes
from .messages import router as message_routes
from .public import router as public_routes
from .public_uploads import router as public_upload_routes
from .transcript import router as transcript_routes


router = APIRouter()
router.include_router(form_routes, tags=["application-forms"])
router.include_router(lifecycle_routes, tags=["applications"])
router.include_router(interview_routes, tags=["applications"])
router.include_router(message_routes, tags=["applications"])
router.include_router(transcript_routes, tags=["applications"])
router.include_router(public_routes, tags=["applications"])
router.include_router(public_upload_routes, tags=["applications"])


__all__ = ["router"]
