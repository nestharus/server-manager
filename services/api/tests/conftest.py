from collections.abc import Iterator, AsyncIterator

import httpx
import pytest
import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router as v1_router
from app.core.factory import create_app
from app.core.settings import Settings


@pytest.fixture(scope="session")
def monkeypatch_session() -> Iterator[MonkeyPatch]:
    monkeypatch = MonkeyPatch()
    yield monkeypatch
    monkeypatch.undo()


@pytest.fixture(scope="session")
def required_env(monkeypatch_session: MonkeyPatch) -> None:
    monkeypatch_session.setenv("DISCORD_BOT_TOKEN", "test-token-value")
    monkeypatch_session.setenv("DISCORD_GUILD_ID", "900000000000000001")
    monkeypatch_session.setenv("SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch_session.setenv("SUPABASE_SERVICE_KEY", "test-service-key")


@pytest.fixture(scope="session")
def test_settings(required_env: None) -> Settings:
    return Settings()


@pytest.fixture()
def app(test_settings: Settings) -> FastAPI:
    application = create_app(settings=test_settings)
    application.include_router(v1_router)
    return application


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
