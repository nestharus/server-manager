"""WU-010C / AC1: API factory + liveness substrate.

Tests fail now and pass after the SLICE-006 code agent implements:
- `services/api/app/contracts/runtime.py` with `ServiceHealthRead`
- `services/api/app/core/factory.py` renamed to `create_api_app`
- `GET /api/v1/health` returning `ServiceHealthRead(status="alive", version=...)`
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio  # noqa: F401 — marker plugin availability

_API_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "api"
if str(_API_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(_API_SERVICE_PATH))

from fastapi import FastAPI  # noqa: E402

from app.contracts.runtime import ServiceHealthRead  # noqa: E402
from app.contracts.runtime_settings import SettingsConstructionError  # noqa: E402
from app.core.factory import create_api_app  # noqa: E402
from app.core.settings import Settings  # noqa: E402


REQUIRED_ENV_VARS = {
    "DISCORD_BOT_TOKEN": "test-token-value",
    "DISCORD_GUILD_ID": "900000000000000001",
    "SUPABASE_DB_URL": "postgresql://user:pass@localhost:5432/db",
    "SUPABASE_SERVICE_KEY": "test-service-key",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)


def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio()
async def test_health_endpoint_returns_alive_with_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()
    app = create_api_app(settings=settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    parsed = ServiceHealthRead.model_validate(response.json())
    assert parsed.status == "alive"
    assert parsed.version == settings.app_version


def test_create_api_app_accepts_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    app = create_api_app(settings=settings)

    assert isinstance(app, FastAPI)
    route_paths = {
        getattr(route, "path", None) for route in app.routes
    }
    assert "/api/v1/health" in route_paths
    assert "/api/v1/metrics" in route_paths
    assert "/api/v1/ready" in route_paths


@pytest.mark.asyncio()
async def test_metrics_endpoint_returns_prometheus_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()
    app = create_api_app(settings=settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "server_manager_api_info" in response.text
    assert f'version="{settings.app_version}"' in response.text
    assert f'channel="{settings.platform_channel}"' in response.text
    assert f'tenant="{settings.platform_tenant}"' in response.text


def test_create_api_app_loads_settings_when_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    app = create_api_app()

    assert isinstance(app, FastAPI)
    assert isinstance(app.state.settings, Settings)


def test_create_api_app_raises_settings_construction_error_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_required_env(monkeypatch)

    with pytest.raises(SettingsConstructionError):
        create_api_app()
