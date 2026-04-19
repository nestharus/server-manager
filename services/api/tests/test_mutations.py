from __future__ import annotations

import json
from typing import Any

import psycopg
import pytest
from pydantic import ValidationError
from psycopg.rows import dict_row

from app.contracts.mutations import (
    MutationRequest,
    MutationResult,
    StaleMutationError,
    StateChangeDraft,
)
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity


TEST_AGGREGATE_TYPE = "test_aggregate"
TEST_AGGREGATE_ID = 101
TEST_PROJECTION_TABLE = "test_mutation_projection"


def _normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _reset_activity_state(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM aggregate_heads")
        conn.execute("DELETE FROM activity_state_changes")
        conn.execute("DELETE FROM activity_actions")


def _seed_head(database_url: str, *, aggregate_id: int, version: int) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO aggregate_heads (aggregate_type, aggregate_id, current_seq, latest_change_id)
            VALUES (%s, %s, %s, NULL)
            """,
            (TEST_AGGREGATE_TYPE, aggregate_id, version),
        )


def _fetch_actions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT id, aggregate_id, status, request_json
            FROM activity_actions
            ORDER BY id
            """
        ).fetchall()
    return [{**row, "request_json": _normalize_json(row["request_json"])} for row in rows]


def _fetch_state_changes(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, aggregate_id, aggregate_seq, change_type, payload_json, diff_json
            FROM activity_state_changes
            ORDER BY id
            """
        ).fetchall()


def _fetch_head(database_url: str, *, aggregate_id: int) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT aggregate_type, aggregate_id, current_seq, latest_change_id
            FROM aggregate_heads
            WHERE aggregate_type = %s AND aggregate_id = %s
            """,
            (TEST_AGGREGATE_TYPE, aggregate_id),
        ).fetchone()

    assert row is not None, f"expected an aggregate head for {TEST_AGGREGATE_TYPE}#{aggregate_id}"
    return row


def _fetch_projection_rows(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            f"SELECT aggregate_id, value FROM {TEST_PROJECTION_TABLE} ORDER BY aggregate_id"
        ).fetchall()


@pytest.fixture()
def mutation_runtime_db(migrated_postgres_db: str) -> Any:
    db = PostgresDatabase(dsn=migrated_postgres_db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def prepared_mutation_db(migrated_postgres_db: str) -> str:
    _reset_activity_state(migrated_postgres_db)

    with psycopg.connect(migrated_postgres_db, autocommit=True) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TEST_PROJECTION_TABLE} (
                aggregate_id BIGINT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(f"TRUNCATE TABLE {TEST_PROJECTION_TABLE}")

    _seed_head(migrated_postgres_db, aggregate_id=TEST_AGGREGATE_ID, version=0)
    yield migrated_postgres_db
    _reset_activity_state(migrated_postgres_db)

    with psycopg.connect(migrated_postgres_db, autocommit=True) as conn:
        conn.execute(f"TRUNCATE TABLE {TEST_PROJECTION_TABLE}")


def test_mutation_request_validation() -> None:
    request = MutationRequest(expected_version=0, actor_kind="user", actor_id="u1")

    assert request.expected_version == 0
    assert request.actor_kind == "user"
    assert request.actor_id == "u1"

    with pytest.raises(ValidationError):
        MutationRequest(expected_version=-1, actor_kind="user", actor_id="u1")

    with pytest.raises(ValidationError):
        MutationRequest(expected_version=0, actor_kind="", actor_id="u1")

    with pytest.raises(ValidationError):
        MutationRequest(expected_version=0, actor_kind="user", actor_id="")


def test_mutation_result_etag_format() -> None:
    result = MutationResult(version=5, etag='"5"')

    assert result.version == 5
    assert result.etag == '"5"'

    with pytest.raises(ValidationError):
        MutationResult(version=5, etag='W/"5"')

    with pytest.raises(ValidationError):
        MutationResult(version=5, etag="5")


def test_state_change_draft_shape() -> None:
    draft = StateChangeDraft(
        change_type="test.updated",
        payload_json={"value": "accepted"},
    )

    assert draft.change_type == "test.updated"
    assert draft.payload_json == {"value": "accepted"}
    assert draft.diff_json is None

    with pytest.raises(ValidationError):
        StateChangeDraft(payload_json={"value": "accepted"})

    with pytest.raises(ValidationError):
        StateChangeDraft(change_type="test.updated")

    with pytest.raises(ValidationError):
        StateChangeDraft(change_type="test.updated", payload_json=["not", "a", "dict"])


def test_stale_mutation_error_carries_context() -> None:
    error = StaleMutationError(
        aggregate_type=TEST_AGGREGATE_TYPE,
        aggregate_id=TEST_AGGREGATE_ID,
        expected_version=2,
        current_version=3,
    )

    assert error.aggregate_type == TEST_AGGREGATE_TYPE
    assert error.aggregate_id == TEST_AGGREGATE_ID
    assert error.expected_version == 2
    assert error.current_version == 3


def test_mutate_entity_accepted_path(
    prepared_mutation_db: str,
    mutation_runtime_db: Any,
) -> None:
    def mutate_projection(tx: Any) -> StateChangeDraft:
        tx.execute(
            f"""
            INSERT INTO {TEST_PROJECTION_TABLE} (aggregate_id, value)
            VALUES (%s, %s)
            """,
            (TEST_AGGREGATE_ID, "accepted"),
        )
        return StateChangeDraft(
            change_type="test.accepted",
            payload_json={"value": "accepted"},
            diff_json={"value": {"before": None, "after": "accepted"}},
        )

    result = mutate_entity(
        db=mutation_runtime_db,
        aggregate_type=TEST_AGGREGATE_TYPE,
        aggregate_id=TEST_AGGREGATE_ID,
        request=MutationRequest(expected_version=0, actor_kind="user", actor_id="u1"),
        action_type="test.accept",
        action_payload={"safe": 1, "secret": "x"},
        payload_allowlist={"safe"},
        mutate_projection=mutate_projection,
    )

    assert result.version == 1
    assert result.etag == '"1"'

    actions = _fetch_actions(prepared_mutation_db)
    state_changes = _fetch_state_changes(prepared_mutation_db)
    head = _fetch_head(prepared_mutation_db, aggregate_id=TEST_AGGREGATE_ID)
    projection_rows = _fetch_projection_rows(prepared_mutation_db)

    assert len(actions) == 1
    assert actions[0]["status"] == "accepted"
    assert len(state_changes) == 1
    assert state_changes[0]["aggregate_seq"] == 1
    assert head["current_seq"] == 1
    assert projection_rows == [{"aggregate_id": TEST_AGGREGATE_ID, "value": "accepted"}]


def test_mutate_entity_stale_version_raises_412_and_audits_rejected(
    prepared_mutation_db: str,
    mutation_runtime_db: Any,
) -> None:
    def mutate_projection(tx: Any) -> StateChangeDraft:
        tx.execute(
            f"""
            INSERT INTO {TEST_PROJECTION_TABLE} (aggregate_id, value)
            VALUES (%s, %s)
            """,
            (TEST_AGGREGATE_ID, "accepted"),
        )
        return StateChangeDraft(
            change_type="test.accepted",
            payload_json={"value": "accepted"},
        )

    accepted = mutate_entity(
        db=mutation_runtime_db,
        aggregate_type=TEST_AGGREGATE_TYPE,
        aggregate_id=TEST_AGGREGATE_ID,
        request=MutationRequest(expected_version=0, actor_kind="user", actor_id="u1"),
        action_type="test.accept",
        action_payload={"safe": 1},
        payload_allowlist={"safe"},
        mutate_projection=mutate_projection,
    )

    assert accepted.version == 1

    with pytest.raises(StaleMutationError) as exc_info:
        mutate_entity(
            db=mutation_runtime_db,
            aggregate_type=TEST_AGGREGATE_TYPE,
            aggregate_id=TEST_AGGREGATE_ID,
            request=MutationRequest(expected_version=0, actor_kind="user", actor_id="u1"),
            action_type="test.accept",
            action_payload={"safe": 2},
            payload_allowlist={"safe"},
            mutate_projection=mutate_projection,
        )

    assert exc_info.value.expected_version == 0
    assert exc_info.value.current_version == 1

    actions = _fetch_actions(prepared_mutation_db)
    state_changes = _fetch_state_changes(prepared_mutation_db)
    head = _fetch_head(prepared_mutation_db, aggregate_id=TEST_AGGREGATE_ID)

    assert [action["status"] for action in actions] == ["accepted", "rejected"]
    assert len(state_changes) == 1
    assert state_changes[0]["aggregate_seq"] == 1
    assert head["current_seq"] == 1


def test_mutate_entity_rollback_on_projection_exception(
    prepared_mutation_db: str,
    mutation_runtime_db: Any,
) -> None:
    class ProjectionBoom(RuntimeError):
        pass

    def mutate_projection(tx: Any) -> StateChangeDraft:
        tx.execute(
            f"""
            INSERT INTO {TEST_PROJECTION_TABLE} (aggregate_id, value)
            VALUES (%s, %s)
            """,
            (TEST_AGGREGATE_ID, "rolled-back"),
        )
        raise ProjectionBoom("projection exploded")

    with pytest.raises(ProjectionBoom):
        mutate_entity(
            db=mutation_runtime_db,
            aggregate_type=TEST_AGGREGATE_TYPE,
            aggregate_id=TEST_AGGREGATE_ID,
            request=MutationRequest(expected_version=0, actor_kind="user", actor_id="u1"),
            action_type="test.accept",
            action_payload={"safe": 1},
            payload_allowlist={"safe"},
            mutate_projection=mutate_projection,
        )

    actions = _fetch_actions(prepared_mutation_db)
    state_changes = _fetch_state_changes(prepared_mutation_db)
    head = _fetch_head(prepared_mutation_db, aggregate_id=TEST_AGGREGATE_ID)
    projection_rows = _fetch_projection_rows(prepared_mutation_db)

    assert len(actions) == 1
    assert actions[0]["status"] == "failed"
    assert state_changes == []
    assert head["current_seq"] == 0
    assert projection_rows == []


def test_mutate_entity_payload_redaction(
    prepared_mutation_db: str,
    mutation_runtime_db: Any,
) -> None:
    def mutate_projection(tx: Any) -> StateChangeDraft:
        tx.execute(
            f"""
            INSERT INTO {TEST_PROJECTION_TABLE} (aggregate_id, value)
            VALUES (%s, %s)
            ON CONFLICT (aggregate_id) DO UPDATE SET value = EXCLUDED.value
            """,
            (TEST_AGGREGATE_ID, "accepted"),
        )
        return StateChangeDraft(
            change_type="test.accepted",
            payload_json={"value": "accepted"},
        )

    first = mutate_entity(
        db=mutation_runtime_db,
        aggregate_type=TEST_AGGREGATE_TYPE,
        aggregate_id=TEST_AGGREGATE_ID,
        request=MutationRequest(expected_version=0, actor_kind="user", actor_id="u1"),
        action_type="test.redact",
        action_payload={"safe": 1, "secret": "x"},
        payload_allowlist={"safe"},
        mutate_projection=mutate_projection,
    )

    second = mutate_entity(
        db=mutation_runtime_db,
        aggregate_type=TEST_AGGREGATE_TYPE,
        aggregate_id=TEST_AGGREGATE_ID,
        request=MutationRequest(expected_version=1, actor_kind="user", actor_id="u1"),
        action_type="test.redact",
        action_payload={"safe": 1, "secret": "x"},
        payload_allowlist=None,
        mutate_projection=mutate_projection,
    )

    assert first.version == 1
    assert second.version == 2

    actions = _fetch_actions(prepared_mutation_db)

    assert actions[0]["request_json"] == {"safe": 1}
    assert actions[1]["request_json"] == {}
