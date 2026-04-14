"""Application factory.

Creates and configures the FastAPI app instance. Called once at
startup. Follows the ai-workflow factory pattern.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.settings import Settings, get_settings
from app.repositories.chapter_repository import AbstractChapterRepository, InMemoryChapterRepository
from app.services.chapter_service import AuditService


def create_app(
    settings: Settings | None = None,
    *,
    chapter_repository: AbstractChapterRepository | None = None,
    audit_service: AuditService | None = None,
) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Humility Server Manager API",
        version="0.1.0",
        docs_url="/docs" if settings.humility_env == "staging" else None,
        redoc_url=None,
    )

    app.state.settings = settings
    app.state.chapter_repository = chapter_repository or InMemoryChapterRepository()
    app.state.audit_service = audit_service or AuditService()

    app.include_router(v1_router, prefix="/api/v1")

    return app
