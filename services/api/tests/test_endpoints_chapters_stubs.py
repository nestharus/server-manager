import importlib
import sys
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factory import create_app
from app.core.settings import Settings


REQUIRED_ENV_VARS = {
    "DISCORD_BOT_TOKEN": "test-token-value",
    "DISCORD_GUILD_ID": "900000000000000001",
    "SUPABASE_DB_URL": "postgresql://user:pass@localhost:5432/db",
    "SUPABASE_SERVICE_KEY": "test-service-key",
}

EXPECTED_ROUTES = {
    ("/api/v1/chapters", "POST"),
    ("/api/v1/chapters", "GET"),
    ("/api/v1/chapters/{chapter_id}", "GET"),
    ("/api/v1/chapters/{chapter_id}", "PATCH"),
    ("/api/v1/chapters/{chapter_id}/archive", "POST"),
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)


def _load_chapters_endpoint_module():
    try:
        return importlib.import_module("app.api.v1.endpoints.chapters")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected endpoint module app.api.v1.endpoints.chapters to exist: {exc}")


def _load_chapters_router() -> APIRouter:
    module = _load_chapters_endpoint_module()
    router = getattr(module, "router", None)

    if router is None:
        pytest.fail("Expected app.api.v1.endpoints.chapters to define `router`.")

    assert isinstance(router, APIRouter)
    return router


def _build_test_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    _set_required_env(monkeypatch)
    settings = Settings()
    app = create_app(settings=settings)
    app.include_router(_load_chapters_router(), tags=["chapters"])
    return app


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/api/v1/chapters", {"name": "Humility Seattle", "slug": "humility-seattle"}),
        ("get", "/api/v1/chapters", None),
        ("get", "/api/v1/chapters/1", None),
        ("patch", "/api/v1/chapters/1", {"version": 0}),
        ("post", "/api/v1/chapters/1/archive", None),
    ],
)
def test_chapter_stub_routes_exist_and_return_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    json_body: dict | None,
) -> None:
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        kwargs = {"json": json_body} if json_body is not None else {}
        response = getattr(client, method)(path, **kwargs)

    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED


def test_chapters_router_is_importable_from_endpoints_module() -> None:
    router = _load_chapters_router()

    assert router is not None


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
