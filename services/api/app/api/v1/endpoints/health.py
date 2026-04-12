"""Health check endpoint.

Returns service status. Used by Railway health checks and the
Discord daemon to verify the API is reachable.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "server-manager-api"}
