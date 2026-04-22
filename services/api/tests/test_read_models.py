from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.mutations import StaleMutationError
from app.repositories.db import PostgresDatabase
from app.repositories.read_models import advance_cursor
from app.services.read_models import (
    MIN_AGE_SECONDS,
    OPERATIONAL_OVERVIEW_PROJECTION_NAME,
    advance_operational_overview_cursor,
)
from app.services.scheduler import SchedulerLoop
from app.tasks.read_models import read_model_worker_tick


def _append_state_change(database_url: str, *, recorded_at: datetime) -> int:
    aggregate_id = f"agg-{uuid4().hex}"
    correlation_id = uuid4()
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
        action_row = conn.execute(
            """
            INSERT INTO activity_actions (
                action_type,
                aggregate_type,
                aggregate_id,
                actor_kind,
                actor_id,
                request_surface,
                request_json,
                status,
                reason_text,
                error_metadata,
                recorded_at,
                correlation_id,
                causation_id,
                scope_kind,
                scope_id
            )
            VALUES (
                'test.action',
                'read_model_test',
                %s,
                'system',
                'test-worker',
                'test:read-models',
                %s,
                'accepted',
                NULL,
                NULL,
                %s,
                %s,
                NULL,
                'global',
                NULL
            )
            RETURNING id
            """,
            (aggregate_id, Jsonb({}), recorded_at, correlation_id),
        ).fetchone()
        assert action_row is not None
        change_row = conn.execute(
            """
            INSERT INTO activity_state_changes (
                action_id,
                aggregate_type,
                aggregate_id,
                aggregate_seq,
                change_type,
                payload_json,
                diff_json,
                recorded_at
            )
            VALUES (%s, 'read_model_test', %s, 1, 'test.changed', %s, NULL, %s)
            RETURNING id
            """,
            (int(action_row["id"]), aggregate_id, Jsonb({"aggregate_id": aggregate_id}), recorded_at),
        ).fetchone()
    assert change_row is not None
    return int(change_row["id"])


def _read_cursor(database_url: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT projection_name,
                   last_processed_id,
                   last_processed_at,
                   version
            FROM read_model_cursors
            WHERE projection_name = %s
            """,
            (OPERATIONAL_OVERVIEW_PROJECTION_NAME,),
        ).fetchone()


def _delete_cursor(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            "DELETE FROM read_model_cursors WHERE projection_name = %s",
            (OPERATIONAL_OVERVIEW_PROJECTION_NAME,),
        )


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def fresh_governance_db(
    fresh_migrated_postgres_db: str,
) -> Iterator[tuple[PostgresDatabase, str]]:
    db = PostgresDatabase(dsn=fresh_migrated_postgres_db)
    try:
        yield db, fresh_migrated_postgres_db
    finally:
        db.close()


def test_projector_advances_cursor_from_seed(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: projector advances the seeded cursor to the settled event head."""
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    expected_ids = [
        _append_state_change(governance_dsn, recorded_at=now - timedelta(seconds=10)),
        _append_state_change(governance_dsn, recorded_at=now - timedelta(seconds=9)),
        _append_state_change(governance_dsn, recorded_at=now - timedelta(seconds=8)),
    ]

    read = advance_operational_overview_cursor(
        governance_db,
        now=now,
        min_age_seconds=MIN_AGE_SECONDS,
    )

    assert read.projection_name == OPERATIONAL_OVERVIEW_PROJECTION_NAME
    assert read.last_processed_id == max(expected_ids)
    assert read.last_processed_at == now
    assert read.version == 1


def test_projector_resumes_from_persisted_cursor(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: projector resumes from the persisted cursor and only advances on new settled events."""
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    first_id = _append_state_change(governance_dsn, recorded_at=now - timedelta(seconds=30))
    first = advance_operational_overview_cursor(governance_db, now=now, min_age_seconds=5)
    second = advance_operational_overview_cursor(
        governance_db,
        now=now + timedelta(seconds=1),
        min_age_seconds=0,
    )
    third_id = _append_state_change(governance_dsn, recorded_at=now - timedelta(seconds=20))
    third = advance_operational_overview_cursor(
        governance_db,
        now=now + timedelta(seconds=2),
        min_age_seconds=0,
    )

    assert first.last_processed_id == first_id
    assert second.last_processed_id == first_id
    assert second.version == 1
    assert third.last_processed_id == third_id
    assert third.version == 2


def test_projector_does_not_advance_past_min_age_fence(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: projector leaves the cursor unchanged when all new events are inside the min-age fence."""
    now = datetime.now(tz=UTC)
    _append_state_change(governance_dsn, recorded_at=now)

    read = advance_operational_overview_cursor(
        governance_db,
        now=now,
        min_age_seconds=MIN_AGE_SECONDS,
    )

    assert read.last_processed_id == 0
    assert read.last_processed_at is None
    assert read.version == 0


def test_advance_cursor_uses_occ_and_raises_stale_mutation_error(
    governance_db: PostgresDatabase,
) -> None:
    """AC1: cursor OCC rejects stale expected_version values."""
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    with governance_db.connection() as connection:
        connection.execute(
            """
            UPDATE read_model_cursors
            SET last_processed_id = 11,
                last_processed_at = %s,
                version = 1
            WHERE projection_name = %s
            """,
            (now, OPERATIONAL_OVERVIEW_PROJECTION_NAME),
        )

    with governance_db.connection() as connection:
        with pytest.raises(StaleMutationError) as exc_info:
            advance_cursor(
                connection,
                projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
                last_processed_id=12,
                last_processed_at=now,
                expected_version=0,
            )

    assert exc_info.value.aggregate_type == "read_model_cursor"
    assert exc_info.value.aggregate_id == OPERATIONAL_OVERVIEW_PROJECTION_NAME
    assert exc_info.value.expected_version == 0
    assert exc_info.value.current_version == 1


def test_read_model_worker_tick_logs_and_swallows_exceptions(
    governance_db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: worker tick logs failures and does not raise into the scheduler."""

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("worker-failed")

    monkeypatch.setattr("app.tasks.read_models.advance_operational_overview_cursor", _boom)

    with caplog.at_level("ERROR", logger="app.tasks.read_models"):
        result = read_model_worker_tick(governance_db, now=datetime(2026, 4, 21, 12, 0, tzinfo=UTC))

    assert result is None
    assert "read-model worker tick failed" in caplog.text


def test_scheduler_invokes_read_model_tick_on_interval(
    governance_db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: scheduler wiring runs the read-model worker when due and skips the immediate repeat."""
    calls: list[datetime] = []

    def _read_model_tick(_db: PostgresDatabase, *, now: datetime) -> None:
        calls.append(now)

    monkeypatch.setattr("app.tasks.read_models.read_model_worker_tick", _read_model_tick)
    monkeypatch.setattr(
        "app.tasks.archive.archive_worker_tick",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.deferred_effects.deferred_effect_worker_tick",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.tasks.ticket_sla.ticket_sla_worker_tick",
        lambda: [],
    )

    async def _run() -> None:
        loop = SchedulerLoop(governance_db, worker_id="worker-read-model")
        first = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
        second = first + timedelta(seconds=5)
        third = first + timedelta(seconds=11)
        await loop._run_read_model_tick_if_due(first)
        await loop._run_read_model_tick_if_due(second)
        await loop._run_read_model_tick_if_due(third)

    asyncio.run(_run())

    assert calls == [
        datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        datetime(2026, 4, 21, 12, 0, 11, tzinfo=UTC),
    ]


def test_cursor_seed_present_after_migration(
    fresh_governance_db: tuple[PostgresDatabase, str],
) -> None:
    """AC1: migration seeds exactly one operational overview cursor row."""
    _db, database_url = fresh_governance_db
    row = _read_cursor(database_url)

    assert row is not None
    assert row["projection_name"] == OPERATIONAL_OVERVIEW_PROJECTION_NAME
    assert int(row["last_processed_id"]) == 0
    assert row["last_processed_at"] is None
    assert int(row["version"]) == 0


def test_projector_service_actor_grant_seeded(
    fresh_governance_db: tuple[PostgresDatabase, str],
) -> None:
    """AC2: migration seeds the read-model projector service-actor grant."""
    _db, database_url = fresh_governance_db
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT grantee_id, scope_kind, scope_id, permissions
            FROM authority_grants
            WHERE grantee_id = 'read-model-projector'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND revoked_at IS NULL
            """
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["grantee_id"] == "read-model-projector"
    assert rows[0]["scope_kind"] == "global"
    assert rows[0]["scope_id"] is None
    assert list(rows[0]["permissions"]) == ["read_model.write"]


def test_projector_raises_cursor_not_seeded_when_row_missing(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC4: projector raises CursorNotSeededError instead of auto-seeding at runtime."""
    _delete_cursor(governance_dsn)

    with pytest.raises(RuntimeError) as exc_info:
        advance_operational_overview_cursor(
            governance_db,
            now=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        )

    assert OPERATIONAL_OVERVIEW_PROJECTION_NAME in str(exc_info.value)
    assert _read_cursor(governance_dsn) is None
