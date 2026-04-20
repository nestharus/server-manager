import importlib
import sys
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

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
    ("/api/v1/chapters", "GET"),
    ("/api/v1/chapters/{chapter_id}", "GET"),
    ("/api/v1/chapters/{chapter_id}", "PATCH"),
    ("/api/v1/chapters/{chapter_id}/archive", "POST"),
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


@pytest.mark.parametrize(
    ("method", "path", "json_body", "expected_status"),
    [
        ("post", "/api/v1/chapters", {"name": "Humility Seattle", "slug": "humility-seattle"}, HTTPStatus.CREATED),
        ("get", "/api/v1/chapters", None, HTTPStatus.OK),
        ("get", "/api/v1/chapters/1", None, HTTPStatus.NOT_FOUND),
        ("patch", "/api/v1/chapters/1", {}, HTTPStatus.PRECONDITION_REQUIRED),
        ("post", "/api/v1/chapters/1/archive", None, HTTPStatus.PRECONDITION_REQUIRED),
    ],
)
def test_chapter_routes_exist_and_exercise_live_http_contract(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    json_body: dict | None,
    expected_status: HTTPStatus,
) -> None:
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        kwargs = {"json": json_body} if json_body is not None else {}
        response = getattr(client, method)(path, **kwargs)

    assert response.status_code == expected_status


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
