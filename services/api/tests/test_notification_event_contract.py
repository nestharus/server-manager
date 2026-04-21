"""Contract tests for WU-003B: notification event envelope foundation.

These tests pin the durable-replay + safe-by-default-redaction behavior
that synthesis D6 and proposal §3 WU-003B specify. They do not peek at
the repository or service internals; they round-trip through real
Postgres via the shared testcontainers fixtures.

AC4 trace: replay-after-restart is exercised by closing the
``PostgresDatabase`` pool and reopening a fresh one against the same
DSN, which is as close to a process restart as a unit test can get
without forking.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import (
    MissingCorrelationContextError,
    MutationRequest,
    StateChangeDraft,
)
from app.contracts.notifications import NotificationEventDraft, NotificationEventRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity
from app.services.notification_events import emit as emit_notification_event
from app.services.notification_events import replay as replay_notification_events


AGGREGATE_TYPE = "test_notification_aggregate"
ACTOR = ActorIdentity(actor_kind="service", actor_id="notification-test")


def _make_audit_context(
    *,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> AuditContextRead:
    cid = correlation_id or uuid4()
    headers = CorrelationHeadersRead(
        x_correlation_id=cid,
        x_causation_id=causation_id,
    )
    return AuditContextRead(
        correlation_id=cid,
        causation_id=causation_id,
        headers=headers,
    )


def _make_request(
    *,
    expected_version: int = 0,
    correlation_id: UUID | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="user",
        actor_id="u1",
        reason_text=None,
        request_surface="service:test.notification",
        correlation_id=correlation_id,
        causation_id=None,
    )


def _make_draft(
    *,
    event_type: str = "test.event",
    scope_kind: str | None = None,
    scope_id: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> NotificationEventDraft:
    return NotificationEventDraft(
        event_type=event_type,
        scope_kind=scope_kind,
        scope_id=scope_id,
        payload_json=payload_json if payload_json is not None else {},
    )


def _fetch_notification_rows(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, event_type, correlation_id, causation_id,
                   scope_kind, scope_id, payload_json, created_at
            FROM notification_events
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# emit() inside mutate_projection — writes in the authoritative transaction
# ---------------------------------------------------------------------------


def test_emit_persists_replayable_envelope_with_correlation_context(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Inside a ``mutate_entity()`` call that resolves correlation to X,
    ``emit(db, event=..., connection=..., payload_allowlist={...})`` must
    persist a
    notification row with ``correlation_id=X`` after the outer transaction
    commits.
    """

    correlation_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        emit_notification_event(
            None,
            event=_make_draft(
                event_type="test.notification.emitted",
                payload_json={"key": "value", "secret": "x"},
            ),
            actor=ACTOR,
            connection=connection,
            payload_allowlist=frozenset({"key"}),
        )
        return StateChangeDraft(
            change_type="test.emit.recorded",
            payload_json={"ok": True},
        )

    with use_audit_context(_make_audit_context(correlation_id=correlation_id)):
        mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id="test:emit:1",
            request=_make_request(expected_version=0),
            action_type="test.emit",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=mutate_projection,
        )

    rows = _fetch_notification_rows(governance_dsn)
    assert len(rows) == 1
    row = rows[0]
    assert row["event_type"] == "test.notification.emitted"
    assert UUID(str(row["correlation_id"])) == correlation_id
    # Only the allowlisted key survives.
    assert row["payload_json"] == {"key": "value"}


# ---------------------------------------------------------------------------
# Redaction polarity (safe-by-default)
# ---------------------------------------------------------------------------


def test_notification_event_emit_redacts_payload_without_allowlist(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``payload_allowlist=None`` persists ``{}`` — the safe-by-default
    polarity that matches ``mutate_entity()``'s redaction seam."""

    ctx = _make_audit_context()
    draft = _make_draft(payload_json={"secret": "x"})

    with use_audit_context(ctx):
        with governance_db.transaction() as connection:
            emit_notification_event(
                None,
                event=draft,
                actor=ACTOR,
                connection=connection,
                payload_allowlist=None,
            )

    rows = _fetch_notification_rows(governance_dsn)
    assert len(rows) == 1
    assert rows[0]["payload_json"] == {}


def test_notification_event_emit_allows_explicit_keys(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """A non-empty allowlist persists exactly those keys from the draft
    payload; everything else is dropped before insert."""

    ctx = _make_audit_context()
    draft = _make_draft(payload_json={"safe": 1, "secret": "x"})

    with use_audit_context(ctx):
        with governance_db.transaction() as connection:
            emit_notification_event(
                None,
                event=draft,
                actor=ACTOR,
                connection=connection,
                payload_allowlist=frozenset({"safe"}),
            )

    rows = _fetch_notification_rows(governance_dsn)
    assert len(rows) == 1
    assert rows[0]["payload_json"] == {"safe": 1}


# ---------------------------------------------------------------------------
# Replay-after-restart (AC4)
# ---------------------------------------------------------------------------


def test_replay_is_semantically_equivalent_after_fresh_database_instance(
    governance_dsn: str,
) -> None:
    """AC4: emit three events in one ``PostgresDatabase`` session; close the
    pool; open a fresh ``PostgresDatabase`` at the same DSN; ``replay(db,
    correlation_id)`` must return the three events in ``(created_at ASC,
    id ASC)`` order with identical payload semantics.
    """

    correlation_id = uuid4()
    ctx = _make_audit_context(correlation_id=correlation_id)

    db = PostgresDatabase(dsn=governance_dsn)
    try:
        with use_audit_context(ctx):
            with db.transaction() as connection:
                emit_notification_event(
                    None,
                    event=_make_draft(event_type="test.event.a", payload_json={"n": 1}),
                    actor=ACTOR,
                    connection=connection,
                    payload_allowlist=frozenset({"n"}),
                )
                emit_notification_event(
                    None,
                    event=_make_draft(event_type="test.event.b", payload_json={"n": 2}),
                    actor=ACTOR,
                    connection=connection,
                    payload_allowlist=frozenset({"n"}),
                )
                emit_notification_event(
                    None,
                    event=_make_draft(event_type="test.event.c", payload_json={"n": 3}),
                    actor=ACTOR,
                    connection=connection,
                    payload_allowlist=frozenset({"n"}),
                )
    finally:
        db.close()

    # Simulate process restart: fresh database client at the same DSN.
    fresh_db = PostgresDatabase(dsn=governance_dsn)
    try:
        replayed = replay_notification_events(fresh_db, correlation_id)
    finally:
        fresh_db.close()

    assert [e.event_type for e in replayed] == [
        "test.event.a",
        "test.event.b",
        "test.event.c",
    ]
    assert [e.payload for e in replayed] == [
        {"n": 1},
        {"n": 2},
        {"n": 3},
    ]
    assert all(isinstance(e, NotificationEventRead) for e in replayed)
    assert all(e.correlation_id == correlation_id for e in replayed)

    # Strict ordering rule: (created_at ASC, id ASC).
    for earlier, later in zip(replayed, replayed[1:], strict=False):
        if earlier.created_at == later.created_at:
            assert earlier.id < later.id or str(earlier.id) < str(later.id)
        else:
            assert earlier.created_at <= later.created_at


# ---------------------------------------------------------------------------
# Strict context requirement
# ---------------------------------------------------------------------------


def test_notification_event_emit_outside_audit_context_raises(
    governance_db: PostgresDatabase,
) -> None:
    """Without an active ContextVar and without a surrounding
    ``use_audit_context(...)``, ``emit()`` must raise
    ``MissingCorrelationContextError`` — never invent a correlation id."""

    with governance_db.transaction() as connection:
        with pytest.raises(MissingCorrelationContextError):
            emit_notification_event(
                None,
                event=_make_draft(payload_json={"k": "v"}),
                actor=ACTOR,
                connection=connection,
                payload_allowlist=None,
            )


# ---------------------------------------------------------------------------
# Mutation-correlation override propagation (Scope F-4 trace)
# ---------------------------------------------------------------------------


def test_notification_emit_inside_mutate_projection_uses_mutation_correlation(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """When the caller passes ``MutationRequest.correlation_id=X`` (overriding
    any outer ContextVar), a notification emitted inside
    ``mutate_projection(connection)`` must persist with ``correlation_id=X``,
    not the outer context's correlation id.
    """

    outer_correlation = uuid4()
    override_correlation = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        emit_notification_event(
            None,
            event=_make_draft(event_type="test.override", payload_json={"k": "v"}),
            actor=ACTOR,
            connection=connection,
            payload_allowlist=frozenset({"k"}),
        )
        return StateChangeDraft(
            change_type="test.override.recorded",
            payload_json={"ok": True},
        )

    with use_audit_context(_make_audit_context(correlation_id=outer_correlation)):
        mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id="test:override:1",
            request=_make_request(
                expected_version=0,
                correlation_id=override_correlation,
            ),
            action_type="test.override",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=mutate_projection,
        )

    rows = _fetch_notification_rows(governance_dsn)
    assert len(rows) == 1
    assert UUID(str(rows[0]["correlation_id"])) == override_correlation
    assert UUID(str(rows[0]["correlation_id"])) != outer_correlation
