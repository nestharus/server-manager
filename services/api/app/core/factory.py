"""Application factory.

Creates and configures the FastAPI app instance. Called once at
startup. Follows the ai-workflow factory pattern.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.actor import ActorMiddleware
from app.core.context import CorrelationMiddleware
from app.core.settings import Settings, load_settings
from app.repositories.activity import InMemoryActionStore, InMemoryStateChangeStore
from app.repositories.chapters import ChapterRepository, InMemoryChapterRepository
from app.repositories.db import PostgresDatabase
from app.services.chapters import ChapterService
from app.services.scheduler import build_scheduler_loop


def create_api_app(
    settings: Settings | None = None,
    *,
    chapter_repository: ChapterRepository | None = None,
    action_store: InMemoryActionStore | None = None,
    state_change_store: InMemoryStateChangeStore | None = None,
    db: PostgresDatabase | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else load_settings()
    resolved_chapter_repository = (
        chapter_repository
        if chapter_repository is not None
        else InMemoryChapterRepository()
    )
    resolved_action_store = (
        action_store if action_store is not None else InMemoryActionStore()
    )
    resolved_state_change_store = (
        state_change_store
        if state_change_store is not None
        else InMemoryStateChangeStore()
    )
    resolved_db = (
        db if db is not None else PostgresDatabase(resolved_settings.supabase_db_url)
    )
    scheduler_loop = build_scheduler_loop(resolved_db, worker_id="api:primary")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler_task = asyncio.create_task(scheduler_loop.run())
        app.state.scheduler_task = scheduler_task
        try:
            yield
        finally:
            try:
                await scheduler_loop.stop()
            finally:
                scheduler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scheduler_task
                resolved_db.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(ActorMiddleware)
    app.add_middleware(CorrelationMiddleware)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        content = detail if isinstance(detail, dict) else {"detail": detail}
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=exc.headers,
        )

    app.state.settings = resolved_settings
    app.state.db = resolved_db
    app.state.scheduler_loop = scheduler_loop
    app.state.activity_action_store = resolved_action_store
    app.state.activity_state_change_store = resolved_state_change_store
    app.state.chapter_service = ChapterService(
        repository=resolved_chapter_repository,
        action_store=resolved_action_store,
        state_change_store=resolved_state_change_store,
    )

    app.include_router(v1_router)
    return app
