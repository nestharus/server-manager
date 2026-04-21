from __future__ import annotations

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories._claim import claim_due_rows
from app.repositories.db import PostgresDatabase
from app.services.deferred_effects import deferred_effect_worker_tick, read_degraded_state_summary
from app.services.notifications_delivery import deliver_envelope


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _insert_rule(dsn: str, *, rule_id: UUID | None = None) -> UUID:
    resolved_rule_id = rule_id or uuid4()
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO notification_rules (
                id,
                trigger_json,
                scope_kind,
                scope_id,
                recipients_json,
                channel,
                template_json,
                actionable,
                grouping,
                enabled
            )
            VALUES (
                %s,
                '{"event_type":"chapter.transition"}'::jsonb,
                'global',
                NULL,
                '{"kind":"discord_users","user_ids":["1001"]}'::jsonb,
                'dm',
                '{"title":"T","body":"B"}'::jsonb,
                FALSE,
                'per_event',
                TRUE
            )
            """,
            (resolved_rule_id,),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type,
                aggregate_id,
                current_seq,
                latest_change_id
            )
            VALUES ('notification_rule', %s, 1, NULL)
            """,
            (str(resolved_rule_id),),
        )
    return resolved_rule_id


def _insert_envelope(
    dsn: str,
    *,
    rule_id: UUID,
    envelope_id: UUID | None = None,
    delivery_status: str = "pending",
    attempts: int = 0,
    max_attempts: int = 3,
    claimed_by: str | None = None,
    claimed_at: datetime | None = None,
    lease_until: datetime | None = None,
) -> UUID:
    resolved_envelope_id = envelope_id or uuid4()
    event_id = uuid4()
    root_correlation_id = uuid4()
    now = datetime.now(UTC)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO notification_events (
                id,
                event_type,
                correlation_id,
                causation_id,
                scope_kind,
                scope_id,
                payload_json,
                created_at
            )
            VALUES (
                %s,
                'chapter.transition',
                %s,
                NULL,
                'chapter',
                'chapter-1',
                '{"chapter_id":"chapter-1","to_state":"active"}'::jsonb,
                %s
            )
            """,
            (event_id, root_correlation_id, now),
        )
        conn.execute(
            """
            INSERT INTO notification_envelopes (
                id,
                rule_id,
                rule_version,
                source_event_id,
                root_correlation_id,
                causation_id,
                grouping,
                recipient_key,
                recipient_discord_id,
                recipient_display,
                channel,
                destination_channel_id,
                template_snapshot_json,
                rendered_title,
                rendered_body,
                actionable,
                delivery_status,
                claimed_by,
                claimed_at,
                lease_until,
                attempts,
                max_attempts,
                last_error_json,
                discord_message_id,
                delivered_at,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                1,
                %s,
                %s,
                NULL,
                'per_event',
                'discord_user:1001',
                '1001',
                '1001',
                'dm',
                NULL,
                '{"title":"T","body":"B"}'::jsonb,
                'T',
                'B',
                FALSE,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                NULL,
                NULL,
                %s,
                %s
            )
            """,
            (
                resolved_envelope_id,
                rule_id,
                event_id,
                root_correlation_id,
                delivery_status,
                claimed_by,
                claimed_at,
                lease_until,
                attempts,
                max_attempts,
                now,
                now,
            ),
        )
    return resolved_envelope_id


def _insert_delivery_effect(
    dsn: str,
    *,
    envelope_id: UUID,
    idempotency_key: str | None = None,
) -> None:
    now = datetime.now(UTC)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO deferred_effects (
                id,
                subsystem,
                effect_type,
                idempotency_key,
                payload_json,
                consequence_level,
                precondition_state,
                status,
                claimed_by,
                claimed_at,
                lease_until,
                attempts,
                max_attempts,
                last_error_json,
                correlation_id,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                'notifications',
                'notifications_deliver',
                %s,
                %s,
                'safe',
                'unchecked',
                'queued',
                NULL,
                NULL,
                NULL,
                0,
                3,
                NULL,
                %s,
                %s,
                %s
            )
            """,
            (
                uuid4(),
                idempotency_key or f"notifications:deliver:{envelope_id}:{uuid4()}",
                Jsonb({"envelope_id": str(envelope_id)}),
                uuid4(),
                now,
                now,
            ),
        )


def _fetch_envelope(dsn: str, envelope_id: UUID) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT id, rule_id, delivery_status, attempts, max_attempts,
                   claimed_by, claimed_at, lease_until, last_error_json,
                   discord_message_id, delivered_at
            FROM notification_envelopes
            WHERE id = %s
            """,
            (envelope_id,),
        ).fetchone()
    assert row is not None
    return row


def _fetch_rule(dsn: str, rule_id: UUID) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT id, trigger_json, recipients_json, channel, template_json,
                   actionable, grouping, enabled
            FROM notification_rules
            WHERE id = %s
            """,
            (rule_id,),
        ).fetchone()
    assert row is not None
    return row


def _fetch_rule_head(dsn: str, rule_id: UUID) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT aggregate_type, aggregate_id, current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'notification_rule'
              AND aggregate_id = %s
            """,
            (str(rule_id),),
        ).fetchone()
    assert row is not None
    return row


def _load_delivery_error_type() -> type[Exception]:
    for module_name in (
        "app.contracts.notifications",
        "app.services.notifications_delivery",
        "app.tasks.notifications_deliver",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        error_type = getattr(module, "NotificationDeliveryError", None)
        if isinstance(error_type, type) and issubclass(error_type, Exception):
            return error_type
    pytest.fail("missing NotificationDeliveryError type")


def _load_delivery_result_type() -> Any:
    for module_name in (
        "app.contracts.notifications",
        "app.services.notifications_delivery",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        result_type = getattr(module, "NotificationDeliveryResult", None)
        if result_type is not None:
            return result_type
    pytest.fail("missing NotificationDeliveryResult contract")


def _patch_delivery_port(monkeypatch: pytest.MonkeyPatch, port: Any) -> None:
    patched = False
    for module_name in ("app.services.notifications_delivery", "app.tasks.notifications_deliver"):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for attribute_name in (
            "delivery_port",
            "_delivery_port",
            "DELIVERY_PORT",
            "get_delivery_port",
            "_get_delivery_port",
            "build_delivery_port",
            "_build_delivery_port",
        ):
            if hasattr(module, attribute_name):
                current = getattr(module, attribute_name)
                if callable(current):
                    monkeypatch.setattr(module, attribute_name, lambda *args, **kwargs: port)
                else:
                    monkeypatch.setattr(module, attribute_name, port)
                patched = True
                break
    if not patched:
        pytest.fail("expected an injectable delivery-port seam in notifications delivery code")


def _register_delivery_handler() -> None:
    try:
        importlib.import_module("app.tasks.notifications_deliver")
    except ModuleNotFoundError as error:
        pytest.fail(f"missing SLICE-015 delivery task module: {error}")


class FakeDeliveryPort:
    def __init__(self, *, result: Any | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[Any] = []

    def deliver(self, command: Any) -> Any:
        self.calls.append(command)
        if self.error is not None:
            raise self.error
        return self.result


def test_claim_due_rows_with_claim_status_none_does_not_set_status(
    governance_dsn: str,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    envelope_id = _insert_envelope(governance_dsn, rule_id=rule_id, delivery_status="pending")
    now = datetime.now(UTC)

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        claimed = claim_due_rows(
            conn,
            table="notification_envelopes",
            primary_key="id",
            worker_id="notification-dispatcher",
            batch_size=5,
            now=now,
            lease_seconds=60,
            ready_predicate=(
                "delivery_status = 'pending' "
                "AND attempts < max_attempts "
                "AND (claimed_by IS NULL OR lease_until < %s)"
            ),
            predicate_params=(now,),
            order_by="created_at ASC, id ASC",
            claim_status=None,
        )
        persisted = conn.execute(
            """
            SELECT delivery_status, claimed_by
            FROM notification_envelopes
            WHERE id = %s
            """,
            (envelope_id,),
        ).fetchone()

    assert len(claimed) == 1
    assert persisted is not None
    assert persisted["delivery_status"] == "pending"
    assert persisted["claimed_by"] == "notification-dispatcher"


def test_delivery_worker_marks_envelope_delivered_exactly_once(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    envelope_id = _insert_envelope(governance_dsn, rule_id=rule_id)
    result_type = _load_delivery_result_type()
    result = result_type(
        envelope_id=envelope_id,
        discord_message_id="discord-msg-1",
        delivered_at=datetime.now(UTC),
    )
    port = FakeDeliveryPort(result=result)
    deliver_envelope(governance_db, envelope_id, delivery_port=port)
    deliver_envelope(governance_db, envelope_id, delivery_port=port)

    envelope = _fetch_envelope(governance_dsn, envelope_id)
    assert len(port.calls) == 1
    assert envelope["delivery_status"] == "delivered"
    assert envelope["discord_message_id"] == "discord-msg-1"
    assert envelope["delivered_at"] is not None


def test_discord_delivery_failure_does_not_mutate_rule(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    before_rule = _fetch_rule(governance_dsn, rule_id)
    before_head = _fetch_rule_head(governance_dsn, rule_id)
    envelope_id = _insert_envelope(governance_dsn, rule_id=rule_id, max_attempts=3)
    error_type = _load_delivery_error_type()
    error = error_type("discord rejected send", definitive_failure=True)
    port = FakeDeliveryPort(error=error)
    deliver_envelope(governance_db, envelope_id, delivery_port=port)

    after_rule = _fetch_rule(governance_dsn, rule_id)
    after_head = _fetch_rule_head(governance_dsn, rule_id)
    envelope = _fetch_envelope(governance_dsn, envelope_id)
    assert after_rule == before_rule
    assert after_head == before_head
    assert envelope["delivery_status"] == "pending"
    assert envelope["attempts"] == 1


def test_retry_attempts_counter_increments_on_failure(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    envelope_id = _insert_envelope(governance_dsn, rule_id=rule_id, attempts=0, max_attempts=2)
    error_type = _load_delivery_error_type()
    port = FakeDeliveryPort(error=error_type("discord unavailable", definitive_failure=True))
    deliver_envelope(governance_db, envelope_id, delivery_port=port)

    envelope = _fetch_envelope(governance_dsn, envelope_id)
    assert envelope["attempts"] == 1
    assert envelope["delivery_status"] == "pending"
    assert envelope["last_error_json"]["message"].startswith("discord unavailable")


def test_degraded_state_summary_counts_stuck_in_flight_envelopes(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    _insert_envelope(
        governance_dsn,
        rule_id=rule_id,
        delivery_status="delivered_in_flight",
        claimed_by="notification-dispatcher",
        claimed_at=datetime.now(UTC) - timedelta(hours=2),
        lease_until=datetime.now(UTC) - timedelta(hours=1, minutes=30),
    )

    summaries = read_degraded_state_summary(governance_db)
    notifications_summary = next(
        (summary for summary in summaries if summary.subsystem == "notifications"),
        None,
    )

    assert notifications_summary is not None
    assert getattr(notifications_summary, "stuck_in_flight_envelopes") == 1
