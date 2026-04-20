import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import httpx
import psycopg
import pytest
import pytest_asyncio
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from app.contracts.testing import API_TEST_HARNESS, ApiTestHarnessRead
from app.core.factory import create_api_app
from app.core.settings import Settings


GOVERNANCE_TABLES = (
    "notification_events",
    "activity_state_changes",
    "activity_actions",
    "aggregate_heads",
    "authority_grants",
    "policy_versions",
    "roster_entries",
    "chapter_roles",
    "chapter_templates",
    "permission_drift",
    "permission_intents",
    "scheduled_jobs",
    "deferred_effects",
)


def reset_governance_state(database_url: str) -> None:
    """Truncate every governance-adjacent table that exists for per-test isolation.

    Only truncates tables present in the database schema, so the fixture is
    safe across branches that have different subsets of the governance
    migrations applied.
    """

    with psycopg.connect(database_url, autocommit=True) as conn:
        existing = [
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(%s)",
                (list(GOVERNANCE_TABLES),),
            ).fetchall()
        ]
        if not existing:
            return
        conn.execute(
            "TRUNCATE TABLE "
            + ", ".join(existing)
            + " RESTART IDENTITY CASCADE"
        )


@pytest.fixture(scope="session")
def monkeypatch_session() -> Iterator[MonkeyPatch]:
    monkeypatch = MonkeyPatch()
    yield monkeypatch
    monkeypatch.undo()


def _normalize_postgres_url(url: str) -> str:
    return url.replace("+psycopg2", "").replace("+psycopg", "")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def api_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16") as container:
        yield container


@pytest.fixture(scope="session")
def postgres_dsn(postgres_container: PostgresContainer) -> str:
    return _normalize_postgres_url(postgres_container.get_connection_url())


@pytest.fixture()
def fresh_postgres_dsn() -> Iterator[str]:
    with PostgresContainer("postgres:16") as container:
        yield _normalize_postgres_url(container.get_connection_url())


@pytest.fixture(scope="session")
def required_env(monkeypatch_session: MonkeyPatch, postgres_dsn: str) -> None:
    monkeypatch_session.setenv("DISCORD_BOT_TOKEN", "test-token-value")
    monkeypatch_session.setenv("DISCORD_GUILD_ID", "900000000000000001")
    monkeypatch_session.setenv("SUPABASE_DB_URL", postgres_dsn)
    monkeypatch_session.setenv("DATABASE_URL", postgres_dsn)
    monkeypatch_session.setenv("SUPABASE_SERVICE_KEY", "test-service-key")


@pytest.fixture(scope="session")
def test_settings(required_env: None) -> Settings:
    return Settings()


@pytest.fixture()
def test_harness() -> ApiTestHarnessRead:
    return API_TEST_HARNESS


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
def fresh_migrated_postgres_db(
    fresh_postgres_dsn: str,
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    result = alembic_runner(fresh_postgres_dsn, "upgrade", "head")
    assert result.returncode == 0, (
        "alembic upgrade head failed for a clean database.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return fresh_postgres_dsn


@pytest.fixture()
def app(test_settings: Settings) -> FastAPI:
    return create_api_app(settings=test_settings)


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest_asyncio.fixture()
async def migrated_async_client(
    migrated_postgres_db: str,  # noqa: ARG001 — forces fixture ordering: migrations run before the client yields
    async_client: httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    yield async_client


@pytest.fixture()
def governance_dsn(migrated_postgres_db: str) -> Iterator[str]:
    """DSN fixture for governance-foundation tests.

    Truncates every governance-related table before each test so no state
    leaks across cases. SLICE-002 tests reuse the session-scoped migrated
    Postgres because migrations are expensive; per-test isolation is done
    through truncation.
    """

    reset_governance_state(migrated_postgres_db)
    yield migrated_postgres_db
    reset_governance_state(migrated_postgres_db)
