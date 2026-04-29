import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

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
from app.repositories.db import PostgresDatabase
from app.core.settings import Settings


GOVERNANCE_TABLES = (
    "notification_events",
    "notification_envelopes",
    "notification_rules",
    "activity_state_changes",
    "activity_actions",
    "aggregate_heads",
    "authority_grants",
    "trust_signals",
    "trust_profiles",
    "members",
    "policy_versions",
    "chapter_archive_runs",
    "chapter_transitions",
    "chapters",
    "roster_transitions",
    "roster_entries",
    "chapter_roles",
    "chapter_templates",
    "ticket_sla_triggers",
    "application_reviews",
    "applications",
    "form_definitions",
    "ticket_messages",
    "ticket_transitions",
    "tickets",
    "ticket_categories",
    "permission_drift",
    "permission_reconciliation_runs",
    "permission_intents",
    "read_model_cursors",
    "scheduled_jobs",
    "deferred_effects",
    "compliance_evaluations",
    "evidence_submissions",
    "compliance_rules",
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
        if "read_model_cursors" in existing:
            conn.execute(
                """
                INSERT INTO read_model_cursors (projection_name)
                VALUES ('operational_overview')
                ON CONFLICT (projection_name) DO NOTHING
                """
            )
        if "authority_grants" in existing:
            conn.execute(
                """
                INSERT INTO authority_grants (
                    id, grantee_id, scope_kind, scope_id, permissions,
                    expires_at, revoked_at, revoked_by, revocation_reason,
                    predecessor_grant_id
                )
                SELECT gen_random_uuid(), 'read-model-projector', 'global', NULL,
                       '["read_model.write"]'::jsonb, NULL, NULL, NULL, NULL, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM authority_grants
                    WHERE grantee_id = 'read-model-projector'
                      AND scope_kind = 'global'
                      AND permissions @> '["read_model.write"]'::jsonb
                      AND permissions <@ '["read_model.write"]'::jsonb
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO authority_grants (
                    id, grantee_id, scope_kind, scope_id, permissions,
                    expires_at, revoked_at, revoked_by, revocation_reason,
                    predecessor_grant_id
                )
                SELECT gen_random_uuid(), 'compliance-evaluator', 'global', NULL,
                       '["compliance_rule.read","compliance_evaluation.write","roster.transition"]'::jsonb,
                       NULL, NULL, NULL, NULL, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM authority_grants
                    WHERE grantee_id = 'compliance-evaluator'
                      AND scope_kind = 'global'
                      AND scope_id IS NULL
                      AND permissions @> '["compliance_rule.read","compliance_evaluation.write","roster.transition"]'::jsonb
                      AND permissions <@ '["compliance_rule.read","compliance_evaluation.write","roster.transition"]'::jsonb
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                )
                """
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


@dataclass(frozen=True)
class SyntheticMemberGuardMember:
    id: UUID
    discord_user_id: str


class SyntheticMemberGuardMemberFactory:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    def create(self, *, discord_user_id: str) -> SyntheticMemberGuardMember:
        member_id = uuid4()
        with self._db.connection() as connection:
            connection.execute(
                """
                INSERT INTO members (id, discord_user_id, joined_at, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (member_id, discord_user_id, datetime.now(UTC)),
            )
            connection.execute(
                """
                INSERT INTO aggregate_heads (
                    aggregate_type, aggregate_id, current_seq, latest_change_id
                )
                VALUES ('member', %s, 1, NULL)
                """,
                (str(member_id),),
            )
        return SyntheticMemberGuardMember(id=member_id, discord_user_id=discord_user_id)

    def real(self) -> SyntheticMemberGuardMember:
        return self.create(discord_user_id=str(10**17 + (uuid4().int % 10**17)))

    def synthetic(self) -> SyntheticMemberGuardMember:
        return self.create(discord_user_id=f"public:{uuid4().hex[:32]}")


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


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def synthetic_member_guard_member_factory(
    governance_db: PostgresDatabase,
) -> SyntheticMemberGuardMemberFactory:
    return SyntheticMemberGuardMemberFactory(governance_db)
