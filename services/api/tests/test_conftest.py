import sys
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import Settings


def test_test_settings_fixture_produces_valid_settings_object(test_settings: Settings) -> None:
    assert isinstance(test_settings, Settings)
    assert test_settings.discord_bot_token
    assert test_settings.discord_guild_id > 0
    assert test_settings.supabase_db_url
    assert test_settings.supabase_service_key


def test_app_fixture_returns_fastapi_instance(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)


@pytest.mark.asyncio()
async def test_app_fixture_has_v1_router_mounted(async_client: httpx.AsyncClient) -> None:
    response = await async_client.get("/api/v1/health")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio()
async def test_client_fixture_can_make_http_requests(async_client: httpx.AsyncClient) -> None:
    response = await async_client.request("GET", "/api/v1/health")

    assert response.request.method == "GET"
    assert response.request.url.path == "/api/v1/health"
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio()
async def test_client_fixture_reaches_health_endpoint(
    async_client: httpx.AsyncClient,
    test_settings: Settings,
) -> None:
    response = await async_client.get("/api/v1/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "status": "alive",
        "version": test_settings.app_version,
    }


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/api/v1/chapters", {"name": "Humility Seattle"}),
        ("get", "/api/v1/chapters/example", None),
        ("post", "/api/v1/chapters/example/transitions", {}),
        ("patch", "/api/v1/chapters/example/discord-resources", {}),
    ],
)
async def test_chapter_endpoints_are_reachable_via_client(
    async_client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    kwargs = {"json": json_body} if json_body is not None else {}
    response = await getattr(async_client, method)(path, **kwargs)

    assert response.status_code in {
        HTTPStatus.CREATED,
        HTTPStatus.OK,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.PRECONDITION_REQUIRED,
        HTTPStatus.UNAUTHORIZED,
    }
