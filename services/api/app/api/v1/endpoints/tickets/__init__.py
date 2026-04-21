from __future__ import annotations

from fastapi import APIRouter

from . import categories, create, messages, reads, transitions

router = APIRouter()
router.include_router(categories.router)
router.include_router(create.router)
router.include_router(messages.router)
router.include_router(reads.router)
router.include_router(transitions.router)

__all__ = ["router"]
