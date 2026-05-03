from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from dependency_injector import providers
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.notifications import NotificationEventDraft
from app.core.container import ApiContainer
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.notification_events import NotificationEventsRepository
from app.repositories.notifications import NotificationsRepository
from app.services.mutations import mutate_entity
from app.services.notification_events import NotificationEventsService
from app.services.notifications_materialize import NotificationsMaterializeService


def _make_audit_context(correlation_id: UUID | None = None) -> AuditContextRead:
    cid = correlation_id or uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=cid,
            x_causation_id=None,
        ),
    )


def _service_actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="service", actor_id="notification-dispatcher")


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _notification_events_service(
    db: PostgresDatabase,
    *,
    deferred_effects_repo: DeferredEffectsRepository | None = None,
) -> NotificationEventsService:
    return NotificationEventsService(
        notification_events_repo=NotificationEventsRepository(db),
        deferred_effects_repo=deferred_effects_repo or DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


def _materialize_service(
    db: PostgresDatabase,
    *,
    deferred_effects_repo: DeferredEffectsRepository | None = None,
) -> NotificationsMaterializeService:
    service = NotificationsMaterializeService(
        notifications_repo=NotificationsRepository(db),
        notification_events_repo=NotificationEventsRepository(db),
        deferred_effects_repo=deferred_effects_repo or DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )
    container = ApiContainer()
    container.core.db.override(providers.Object(db))
    container.services.notifications_materialize.override(providers.Object(service))
    try:
        return container.services.notifications_materialize()
    finally:
        container.services.notifications_materialize.reset_override()
        container.core.db.reset_override()


def _insert_rule(
    dsn: str,
    *,
    rule_id: UUID | None = None,
    version: int = 1,
    trigger_json: dict[str, Any] | None = None,
    scope_kind: str = "global",
    scope_id: str | None = None,
    recipients_json: dict[str, Any] | None = None,
    channel: str = "dm",
    template_json: dict[str, Any] | None = None,
    actionable: bool = False,
    grouping: str = "per_event",
    enabled: bool = True,
) -> UUID:
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                resolved_rule_id,
                Jsonb(trigger_json or {"event_type": "chapter.transition"}),
                scope_kind,
                scope_id,
                Jsonb(recipients_json or {"kind": "discord_users", "user_ids": ["1001"]}),
                channel,
                Jsonb(
                    template_json
                    or {
                        "title": "Chapter ${payload_chapter_id}",
                        "body": "Moved to ${payload_to_state}",
                    }
                ),
                actionable,
                grouping,
                enabled,
            ),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type,
                aggregate_id,
                current_seq,
                latest_change_id
            )
            VALUES ('notification_rule', %s, %s, NULL)
            """,
            (str(resolved_rule_id), version),
        )
    return resolved_rule_id


def _insert_event(
    dsn: str,
    *,
    event_id: UUID | None = None,
    event_type: str = "chapter.transition",
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    scope_kind: str | None = "chapter",
    scope_id: str | None = "chapter-1",
    payload_json: dict[str, Any] | None = None,
) -> UUID:
    resolved_event_id = event_id or uuid4()
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
                payload_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                resolved_event_id,
                event_type,
                correlation_id or uuid4(),
                causation_id,
                scope_kind,
                scope_id,
                Jsonb(
                    payload_json
                    or {"chapter_id": "chapter-1", "to_state": "active", "member_id": "m-1"}
                ),
            ),
        )
    return resolved_event_id


def _fetch_event_correlation(dsn: str, event_id: UUID) -> UUID:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT correlation_id
            FROM notification_events
            WHERE id = %s
            """,
            (event_id,),
        ).fetchone()
    assert row is not None
    return UUID(str(row["correlation_id"]))


def _fetch_envelopes(
    dsn: str,
    *,
    rule_id: UUID | None = None,
    source_event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    clauses = ["TRUE"]
    params: list[Any] = []
    if rule_id is not None:
        clauses.append("rule_id = %s")
        params.append(rule_id)
    if source_event_id is not None:
        clauses.append("source_event_id = %s")
        params.append(source_event_id)
    where = " AND ".join(clauses)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            f"""
            SELECT id, rule_id, rule_version, source_event_id, root_correlation_id,
                   grouping, recipient_key, recipient_discord_id, recipient_display,
                   channel, destination_channel_id, template_snapshot_json,
                   rendered_title, rendered_body, actionable, delivery_status,
                   attempts, max_attempts, last_error_json
            FROM notification_envelopes
            WHERE {where}
            ORDER BY created_at ASC, id ASC
            """,
            tuple(params),
        ).fetchall()


def _fetch_deferred_effects(dsn: str, *, effect_type: str) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, effect_type, idempotency_key, payload_json, status
            FROM deferred_effects
            WHERE effect_type = %s
            ORDER BY created_at ASC, id ASC
            """,
            (effect_type,),
        ).fetchall()


def _update_rule_json(
    dsn: str,
    rule_id: UUID,
    *,
    recipients_json: dict[str, Any] | None = None,
    template_json: dict[str, Any] | None = None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []
    if recipients_json is not None:
        sets.append("recipients_json = %s")
        params.append(Jsonb(recipients_json))
    if template_json is not None:
        sets.append("template_json = %s")
        params.append(Jsonb(template_json))
    params.append(rule_id)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            f"UPDATE notification_rules SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
        )


def test_notification_migration_creates_tables_and_partial_unique_indexes(
    governance_dsn: str,
) -> None:
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        tables = {
            row["table_name"]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('notification_rules', 'notification_envelopes')
                """
            ).fetchall()
        }
        indexes = {
            row["indexname"]: row["indexdef"].lower()
            for row in conn.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN (
                    'uq_notification_envelopes__per_event',
                    'uq_notification_envelopes__per_root_cause'
                  )
                """
            ).fetchall()
        }

    assert tables == {"notification_rules", "notification_envelopes"}
    assert "uq_notification_envelopes__per_event" in indexes
    assert "source_event_id" in indexes["uq_notification_envelopes__per_event"]
    assert "recipient_key" in indexes["uq_notification_envelopes__per_event"]
    assert "grouping" in indexes["uq_notification_envelopes__per_event"]
    assert "per_event" in indexes["uq_notification_envelopes__per_event"]
    assert "uq_notification_envelopes__per_root_cause" in indexes
    assert "root_correlation_id" in indexes["uq_notification_envelopes__per_root_cause"]
    assert "recipient_key" in indexes["uq_notification_envelopes__per_root_cause"]
    assert "grouping" in indexes["uq_notification_envelopes__per_root_cause"]
    assert "per_root_cause" in indexes["uq_notification_envelopes__per_root_cause"]


def test_emit_is_atomic_when_called_with_connection(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("deferred enqueue failed")

    deferred_effects_repo = DeferredEffectsRepository(governance_db)
    monkeypatch.setattr(deferred_effects_repo, "_enqueue_effect_on", boom)
    notification_events_service = _notification_events_service(
        governance_db,
        deferred_effects_repo=deferred_effects_repo,
    )
    draft = NotificationEventDraft(
        event_type="chapter.transition",
        scope_kind="chapter",
        scope_id="chapter-1",
        payload_json={"chapter_id": "chapter-1", "to_state": "active"},
    )

    with use_audit_context(_make_audit_context()):
        with pytest.raises(RuntimeError, match="deferred enqueue failed"):
            with governance_db.transaction() as connection:
                notification_events_service.emit(
                    connection,
                    event=draft,
                    actor=_service_actor(),
                )

    with psycopg.connect(governance_dsn) as conn:
        event_count = conn.execute("SELECT COUNT(*) FROM notification_events").fetchone()[0]
        effect_count = conn.execute("SELECT COUNT(*) FROM deferred_effects").fetchone()[0]

    assert int(event_count) == 0
    assert int(effect_count) == 0


def test_materialize_enqueues_delivery_effects_in_one_transaction(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule_id = _insert_rule(governance_dsn)
    event_id = _insert_event(governance_dsn)

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("delivery enqueue failed")

    deferred_effects_repo = DeferredEffectsRepository(governance_db)
    monkeypatch.setattr(deferred_effects_repo, "_enqueue_effect_on", boom)
    service = _materialize_service(
        governance_db,
        deferred_effects_repo=deferred_effects_repo,
    )

    with pytest.raises(RuntimeError, match="delivery enqueue failed"):
        service.materialize_event(event_id, worker_id="notification-dispatcher")

    assert _fetch_envelopes(governance_dsn, rule_id=rule_id) == []
    assert _fetch_deferred_effects(governance_dsn, effect_type="notifications_deliver") == []


def test_per_event_rule_emits_one_envelope_per_event(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, grouping="per_event")
    correlation_id = uuid4()
    first = _insert_event(governance_dsn, correlation_id=correlation_id)
    second = _insert_event(governance_dsn, correlation_id=correlation_id)

    service.materialize_event(first, worker_id="notification-dispatcher")
    service.materialize_event(second, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 2
    assert {UUID(str(row["source_event_id"])) for row in envelopes} == {first, second}
    assert {row["grouping"] for row in envelopes} == {"per_event"}


def test_per_root_cause_rule_emits_one_envelope_per_root_correlation(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    correlation_id = uuid4()
    rule_id = _insert_rule(governance_dsn, grouping="per_root_cause")
    event_id = _insert_event(governance_dsn, correlation_id=correlation_id)

    service.materialize_event(event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 1
    assert UUID(str(envelopes[0]["root_correlation_id"])) == correlation_id
    assert envelopes[0]["grouping"] == "per_root_cause"


def test_multiple_events_same_root_correlation_produce_one_envelope(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, grouping="per_root_cause")
    correlation_id = uuid4()
    first = _insert_event(governance_dsn, correlation_id=correlation_id)
    second = _insert_event(governance_dsn, correlation_id=correlation_id)

    service.materialize_event(first, worker_id="notification-dispatcher")
    service.materialize_event(second, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 1
    assert UUID(str(envelopes[0]["root_correlation_id"])) == correlation_id


def test_different_root_correlations_produce_separate_envelopes(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, grouping="per_root_cause")
    first = _insert_event(governance_dsn, correlation_id=uuid4())
    second = _insert_event(governance_dsn, correlation_id=uuid4())

    service.materialize_event(first, worker_id="notification-dispatcher")
    service.materialize_event(second, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 2
    assert {
        UUID(str(row["root_correlation_id"]))
        for row in envelopes
    } == {
        _fetch_event_correlation(governance_dsn, first),
        _fetch_event_correlation(governance_dsn, second),
    }


def test_replay_same_event_does_not_create_duplicate_envelopes(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, grouping="per_event")
    event_id = _insert_event(governance_dsn)

    service.materialize_event(event_id, worker_id="notification-dispatcher")
    service.materialize_event(event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id, source_event_id=event_id)
    delivery_effects = _fetch_deferred_effects(
        governance_dsn,
        effect_type="notifications_deliver",
    )
    assert len(envelopes) == 1
    assert len(delivery_effects) == 1


def test_materialize_is_idempotent_under_retry(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, grouping="per_root_cause")
    correlation_id = uuid4()
    event_id = _insert_event(governance_dsn, correlation_id=correlation_id)

    service.materialize_event(event_id, worker_id="notification-dispatcher")
    service.materialize_event(event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    delivery_effects = _fetch_deferred_effects(
        governance_dsn,
        effect_type="notifications_deliver",
    )
    assert len(envelopes) == 1
    assert len(delivery_effects) == 1
    assert delivery_effects[0]["payload_json"] == {"envelope_id": str(envelopes[0]["id"])}


def test_recipient_resolution_at_materialization_time(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(
        governance_dsn,
        recipients_json={"kind": "discord_users", "user_ids": ["1001", "1002"]},
    )
    event_id = _insert_event(governance_dsn)

    service.materialize_event(event_id, worker_id="notification-dispatcher")
    _update_rule_json(
        governance_dsn,
        rule_id,
        recipients_json={"kind": "discord_users", "user_ids": ["2001"]},
    )

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert {row["recipient_key"] for row in envelopes} == {
        "discord_user:1001",
        "discord_user:1002",
    }
    assert {row["recipient_discord_id"] for row in envelopes} == {"1001", "1002"}


def test_template_rendering_snapshot_isolates_from_later_rule_edits(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    original_template = {
        "title": "Original ${payload_chapter_id}",
        "body": "State ${payload_to_state}",
    }
    rule_id = _insert_rule(governance_dsn, template_json=original_template)
    event_id = _insert_event(governance_dsn)

    service.materialize_event(event_id, worker_id="notification-dispatcher")
    _update_rule_json(
        governance_dsn,
        rule_id,
        template_json={"title": "Edited ${event_type}", "body": "Edited body"},
    )

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 1
    assert envelopes[0]["template_snapshot_json"] == original_template
    assert envelopes[0]["rendered_title"] == "Original chapter-1"
    assert envelopes[0]["rendered_body"] == "State active"


def test_materialize_skips_rules_when_enabled_false(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(governance_dsn, enabled=False)
    event_id = _insert_event(governance_dsn)

    service.materialize_event(event_id, worker_id="notification-dispatcher")

    assert _fetch_envelopes(governance_dsn, rule_id=rule_id) == []
    assert _fetch_deferred_effects(governance_dsn, effect_type="notifications_deliver") == []


def test_materialize_skips_when_template_missing_key(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    service = _materialize_service(governance_db)
    rule_id = _insert_rule(
        governance_dsn,
        template_json={
            "title": "Missing ${payload_missing_key}",
            "body": "State ${payload_to_state}",
        },
    )
    event_id = _insert_event(governance_dsn)

    service.materialize_event(event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes(governance_dsn, rule_id=rule_id)
    assert len(envelopes) == 1
    assert envelopes[0]["delivery_status"] == "skipped"
    assert envelopes[0]["last_error_json"]["reason"] == "template_missing_key"
    assert _fetch_deferred_effects(governance_dsn, effect_type="notifications_deliver") == []
