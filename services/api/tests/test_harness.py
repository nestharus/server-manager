"""Contract-level tests for the API test harness (WU-009A).

Asserts that the `ApiTestHarnessRead` contract and `API_TEST_HARNESS` constant
correctly describe the fixtures actually provided by `services/api/tests/conftest.py`.
"""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI

import httpx

from app.contracts.testing import ApiTestHarnessRead, API_TEST_HARNESS


def test_api_test_harness_contract_field_shape() -> None:
    assert isinstance(API_TEST_HARNESS, ApiTestHarnessRead)
    assert API_TEST_HARNESS.app_fixture_name == "app"
    assert API_TEST_HARNESS.async_client_fixture_names == frozenset(
        {"async_client", "migrated_async_client"}
    )
    assert API_TEST_HARNESS.db_dsn_fixture_names == frozenset(
        {"migrated_postgres_db", "governance_dsn"}
    )
    assert API_TEST_HARNESS.audit_context_helper == "app.core.context:use_audit_context"


def test_app_fixture_resolves(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)


@pytest.mark.asyncio()
async def test_async_client_fixture_yields_async_client(
    async_client: httpx.AsyncClient,
) -> None:
    assert isinstance(async_client, httpx.AsyncClient)


@pytest.mark.asyncio()
async def test_migrated_async_client_runs_migrations(
    migrated_async_client: httpx.AsyncClient,
    app: FastAPI,
) -> None:
    revision = app.state.container.core.db().current_revision()

    assert isinstance(revision, str)
    assert revision


def test_governance_dsn_truncates_governance_tables_before_yield(
    migrated_postgres_db: str,
    request: pytest.FixtureRequest,
) -> None:
    with psycopg.connect(migrated_postgres_db, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO activity_actions (
                action_type,
                aggregate_type,
                aggregate_id,
                actor_kind,
                actor_id,
                request_surface,
                status,
                correlation_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("probe", "probe", 1, "system", "probe-actor", "probe", "accepted", uuid4()),
        )
        seeded_count = conn.execute(
            "SELECT COUNT(*) FROM activity_actions"
        ).fetchone()[0]
    assert seeded_count >= 1

    dsn = request.getfixturevalue("governance_dsn")

    with psycopg.connect(dsn, autocommit=True) as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM activity_actions"
        ).fetchone()[0]

    assert remaining == 0


def test_use_audit_context_helper_is_importable() -> None:
    import app.core.context as c

    assert callable(c.use_audit_context)


def test_test_harness_fixture_returns_api_test_harness(
    test_harness: ApiTestHarnessRead,
) -> None:
    assert test_harness is API_TEST_HARNESS
