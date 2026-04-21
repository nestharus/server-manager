import importlib
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factory import create_api_app
from app.core.settings import Settings


REQUIRED_ENV_VARS = {
    "DISCORD_BOT_TOKEN": "test-token-value",
    "DISCORD_GUILD_ID": "900000000000000001",
    "SUPABASE_DB_URL": "postgresql://user:pass@localhost:5432/db",
    "SUPABASE_SERVICE_KEY": "test-service-key",
}

EXPECTED_ROUTES = {
    ("/api/v1/chapters", "POST"),
    ("/api/v1/chapters/{chapter_id}", "GET"),
    ("/api/v1/chapters/{chapter_id}/transitions", "POST"),
    ("/api/v1/chapters/{chapter_id}/discord-resources", "PATCH"),
    ("/api/v1/chapter-templates", "POST"),
    ("/api/v1/chapter-templates/{template_id}", "GET"),
    ("/api/v1/chapter-templates/{template_id}", "PATCH"),
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)


def _load_chapters_router() -> APIRouter:
    module = importlib.import_module("app.api.v1.endpoints.chapters")
    router = getattr(module, "router", None)
    assert isinstance(router, APIRouter)
    return router


def _build_test_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    _set_required_env(monkeypatch)
    settings = Settings()
    return create_api_app(settings=settings)


def test_chapters_router_exposes_expected_route_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_test_app(monkeypatch)

    actual_routes = {
        (route.path, method)
        for route in app.router.routes
        if hasattr(route, "methods")
        for method in route.methods
        if method in {"GET", "POST", "PATCH"}
    }

    assert EXPECTED_ROUTES <= actual_routes
