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
from app.repositories.db import PostgresDatabase
from app.services.scheduler import build_scheduler_loop
from app.tasks import configure_task_runtime


def create_api_app(
    settings: Settings | None = None,
    *,
    db: PostgresDatabase | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else load_settings()
    resolved_db = (
        db if db is not None else PostgresDatabase(resolved_settings.supabase_db_url)
    )
    configure_task_runtime(db=resolved_db)
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

    app.include_router(v1_router)
    return app
