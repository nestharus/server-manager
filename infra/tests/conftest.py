from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch


def _normalize_postgres_url(url: str) -> str:
    return url.replace("+psycopg2", "").replace("+psycopg", "")


@pytest.fixture(scope="session")
def monkeypatch_session() -> Iterator[MonkeyPatch]:
    monkeypatch = MonkeyPatch()
    yield monkeypatch
    monkeypatch.undo()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def api_root(repo_root: Path) -> Path:
    return repo_root / "services" / "api"


@pytest.fixture(scope="session")
def api_import_path(api_root: Path) -> None:
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[object]:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as container:
        yield container


@pytest.fixture(scope="session")
def postgres_dsn(postgres_container: object) -> str:
    return _normalize_postgres_url(postgres_container.get_connection_url())


@pytest.fixture(scope="session")
def required_env(
    monkeypatch_session: MonkeyPatch,
    postgres_dsn: str,
    api_import_path: None,
) -> None:
    monkeypatch_session.setenv("DISCORD_BOT_TOKEN", "test-token-value")
    monkeypatch_session.setenv("DISCORD_GUILD_ID", "900000000000000001")
    monkeypatch_session.setenv("SUPABASE_DB_URL", postgres_dsn)
    monkeypatch_session.setenv("DATABASE_URL", postgres_dsn)
    monkeypatch_session.setenv("SUPABASE_SERVICE_KEY", "test-service-key")


@pytest.fixture(scope="session")
def alembic_runner(
    repo_root: Path,
    api_root: Path,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        pythonpath_entries = [str(api_root)]
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            pythonpath_entries.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
        env["SUPABASE_DB_URL"] = database_url
        env["DATABASE_URL"] = database_url

        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(repo_root / "alembic.ini"), *args],
            cwd=repo_root,
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )

    return run


@pytest.fixture(scope="session")
def migrated_postgres_db(
    postgres_dsn: str,
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    result = alembic_runner(postgres_dsn, "upgrade", "head")
    assert result.returncode == 0, (
        "alembic upgrade head failed for the session database.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return postgres_dsn


@pytest.fixture()
def test_settings(required_env: None, api_import_path: None):
    from app.core.settings import Settings

    return Settings()


@pytest.fixture()
def app(test_settings, migrated_postgres_db: str) -> Iterator[object]:
    from app.core.factory import create_api_app

    application = create_api_app(settings=test_settings)
    yield application


@pytest_asyncio.fixture()
async def async_client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client


@pytest_asyncio.fixture()
async def migrated_async_client(
    migrated_postgres_db: str,  # noqa: ARG001
    async_client: httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    yield async_client
