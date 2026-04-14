"""Application factory.

Creates and configures the FastAPI app instance. Called once at
startup. Follows the ai-workflow factory pattern.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.settings import Settings
from app.repositories.chapters import ChapterRepository, InMemoryChapterRepository
from app.services.chapters import ChapterService


def create_app(
    settings: Settings | None = None,
    *,
    chapter_repository: ChapterRepository | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else Settings()
    resolved_chapter_repository = (
        chapter_repository
        if chapter_repository is not None
        else InMemoryChapterRepository()
    )

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
    )
    app.state.settings = resolved_settings
    app.state.chapter_service = ChapterService(
        repository=resolved_chapter_repository
    )
    app.include_router(v1_router)
    return app
