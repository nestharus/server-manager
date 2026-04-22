"""V1 API router.

All v1 endpoints are mounted here. Each endpoint module lives in
app/api/v1/endpoints/.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    applications,
    audit,
    authority,
    chapter_templates,
    chapters,
    health,
    members,
    notifications,
    operations,
    permissions,
    policies,
    ready,
    roster,
    system,
    tickets,
    trust,
)

router = APIRouter()
router.include_router(applications.router)
router.include_router(audit.router, tags=["audit"])
router.include_router(authority.router, tags=["authority"])
router.include_router(chapter_templates.router, tags=["chapter-templates"])
router.include_router(chapters.router, tags=["chapters"])
router.include_router(health.router, tags=["health"])
router.include_router(members.router, tags=["members"])
router.include_router(notifications.router, tags=["notification-rules"])
router.include_router(operations.router, tags=["operations"])
router.include_router(permissions.router)
router.include_router(policies.router, tags=["policies"])
router.include_router(ready.router, tags=["ready"])
router.include_router(roster.router, tags=["roster"])
router.include_router(system.router, tags=["system"])
router.include_router(tickets.router, tags=["tickets"])
router.include_router(trust.router, tags=["trust"])
