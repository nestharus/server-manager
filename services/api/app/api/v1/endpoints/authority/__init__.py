from __future__ import annotations

from fastapi import APIRouter

from . import handoff_applications, handoff_tickets, leadership_context, lifecycle, succession_plan, transfer


router = APIRouter()
router.include_router(lifecycle.router)
router.include_router(succession_plan.router)
router.include_router(transfer.router)
router.include_router(handoff_applications.router)
router.include_router(handoff_tickets.router)
router.include_router(leadership_context.router)

__all__ = ["router"]
