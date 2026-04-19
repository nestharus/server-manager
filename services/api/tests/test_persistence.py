from __future__ import annotations

import subprocess
from collections.abc import Callable

import psycopg
import pytest
from httpx import AsyncClient


def _assert_alembic_ok(result: subprocess.CompletedProcess[str], *, action: str) -> None:
    assert result.returncode == 0, (
        f"alembic {action} failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _alembic_head_revision(
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
    database_url: str,
) -> str:
    result = alembic_runner(database_url, "heads")
    _assert_alembic_ok(result, action="heads")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one Alembic head, got: {lines}"
    return lines[0].split()[0]


def _current_database_revision(database_url: str) -> str:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()

    assert row is not None, "expected alembic_version to contain one current revision row"
    return row[0]


@pytest.mark.asyncio
async def test_migration_status_returns_current_revision(
    migrated_postgres_db: str,
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
    migrated_async_client: AsyncClient,
) -> None:
    head_revision = _alembic_head_revision(alembic_runner, migrated_postgres_db)
    current_revision = _current_database_revision(migrated_postgres_db)

    assert current_revision == head_revision

    response = await migrated_async_client.get("/api/v1/system/migrations/current")

    assert response.status_code == 200
    assert response.json() == {"revision": current_revision}


@pytest.mark.asyncio
async def test_migration_status_contract_shape(
    migrated_postgres_db: str,
    migrated_async_client: AsyncClient,
) -> None:
    expected_revision = _current_database_revision(migrated_postgres_db)

    response = await migrated_async_client.get("/api/v1/system/migrations/current")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"revision"}
    assert isinstance(body["revision"], str)
    assert body["revision"] == expected_revision


def test_clean_database_upgrades_to_head(
    fresh_migrated_postgres_db: str,
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    head_revision = _alembic_head_revision(alembic_runner, fresh_migrated_postgres_db)
    current_revision = _current_database_revision(fresh_migrated_postgres_db)

    assert current_revision == head_revision
