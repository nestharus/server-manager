"""Health check endpoint.

Returns service status. Used by Railway health checks and the
Discord daemon to verify the API is reachable.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/health")


@router.get("")
def healthcheck(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
