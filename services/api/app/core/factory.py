"""Application factory.

Creates and configures the FastAPI app instance. Called once at
startup. Follows the ai-workflow factory pattern.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import suppress

from dependency_injector import providers
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.actor import ActorMiddleware
from app.core.container import ApiContainer
from app.core.context import CorrelationMiddleware
from app.core.settings import Settings, load_settings
from app.infrastructure.authz import CedarAuthorizationClient
from app.infrastructure.ocr import OcrProvider
from app.repositories.db import PostgresDatabase
from app.tasks import configure_task_runtime


def create_api_app(
    settings: Settings | None = None,
    *,
    db: PostgresDatabase | None = None,
    ocr_provider: OcrProvider | None = None,
    cedar_authorizer: CedarAuthorizationClient | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else load_settings()
    container = ApiContainer(settings=resolved_settings)

    if db is not None:
        container.core.db.override(providers.Object(db))
    if cedar_authorizer is not None:
        container.infra.cedar_authorizer.override(providers.Object(cedar_authorizer))
    if ocr_provider is not None:
        container.infra.ocr_provider.override(providers.Object(ocr_provider))

    container.init_resources()

    resolved_db = container.core.db()
    resolved_cedar_authorizer = container.infra.cedar_authorizer()
    resolved_ocr_provider = container.infra.ocr_provider()
    scheduler_loop = container.tasks.scheduler_loop()

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
                container.shutdown_resources()

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

    app.state.container = container
    container.wire(
        modules=[
            "app.api.v1.endpoints.operations",
            "app.api.v1.endpoints.permissions._shared",
            "app.api.v1.endpoints.permissions.drift",
            "app.api.v1.endpoints.permissions.intents",
            "app.api.v1.endpoints.permissions.reconciliation",
            "app.api.v1.endpoints.permissions.temporary",
            "app.api.v1.endpoints.applications.forms",
            "app.api.v1.endpoints.applications.interviews",
            "app.api.v1.endpoints.applications.lifecycle",
            "app.api.v1.endpoints.applications.messages",
            "app.api.v1.endpoints.applications.public",
            "app.api.v1.endpoints.applications.public_uploads",
            "app.api.v1.endpoints.applications.transcript",
            "app.api.v1.endpoints.chapter_templates",
            "app.api.v1.endpoints.chapters.archive",
            "app.api.v1.endpoints.chapters.base",
            "app.api.v1.endpoints.chapters.governance",
            "app.api.v1.endpoints.authority.handoff_applications",
            "app.api.v1.endpoints.authority.handoff_tickets",
            "app.api.v1.endpoints.authority.leadership_context",
            "app.api.v1.endpoints.authority.lifecycle",
            "app.api.v1.endpoints.authority.succession_plan",
            "app.api.v1.endpoints.authority.transfer",
            "app.api.v1.endpoints.members",
            "app.api.v1.endpoints.policies",
            "app.api.v1.endpoints.roster",
            "app.api.v1.endpoints.trust._shared",
            "app.api.v1.endpoints.trust.profiles",
            "app.api.v1.endpoints.trust.recompute",
            "app.api.v1.endpoints.trust.signals",
            "app.core.dependencies",
            "app.api.v1.endpoints.public_application_forms",
            "app.api.v1.endpoints.public_chapters",
            "app.api.v1.endpoints.web",
            "app.api.v1.endpoints.tickets.categories",
            "app.api.v1.endpoints.tickets.create",
            "app.api.v1.endpoints.tickets.messages",
            "app.api.v1.endpoints.tickets.reads",
            "app.api.v1.endpoints.tickets.transitions",
        ],
    )
    # transitional: removed in INIT-142d (synthesis R7d)
    app.state.settings = resolved_settings
    app.state.db = resolved_db
    app.state.cedar_authorizer = resolved_cedar_authorizer
    app.state.ocr_provider = resolved_ocr_provider
    app.state.scheduler_loop = scheduler_loop

    configure_task_runtime(db=resolved_db)

    app.include_router(v1_router)
    return app
