from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from dependency_injector import providers
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.contracts.notifications import NotificationEventDraft, NotificationEventRead
from app.contracts.ticket_categories import TicketCategoryCreate
from app.contracts.ticket_messages import TicketMessageAppendRequest
from app.contracts.tickets import TicketCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.ticket_sla import (
    SLA_NOTIFICATION_PAYLOAD_ALLOWLIST,
    TicketSlaService,
)
from app.services.tickets import TicketsService


def _audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _actor(actor_id: str = "operator") -> ActorIdentity:
    return ActorIdentity(actor_kind="user", actor_id=actor_id)


def _state_machine() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "initial_state": "open",
        "states": [
            {"key": "open", "label": "Open", "terminal": False},
            {"key": "triaged", "label": "Triaged", "terminal": False},
            {"key": "escalated", "label": "Escalated", "terminal": False},
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": [
            {
                "from": "open",
                "to": "triaged",
                "action": "triage",
                "requires_reason": False,
                "requires_resolution": False,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
            {
                "from": "triaged",
                "to": "closed",
                "action": "close",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
            {
                "from": "open",
                "to": "escalated",
                "action": "escalate",
                "requires_reason": False,
                "requires_resolution": False,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
            {
                "from": "escalated",
                "to": "closed",
                "action": "resolve",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
        ],
    }


def _category_payload(*, sla_rules: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": f"SLA Category {uuid4().hex[:8]}",
        "routing_scope": {
            "scope_kind": "chapter",
            "scope_id": "chapter-1",
            "queue": "officers",
        },
        "privacy_level": "reporter_staff",
        "state_machine": _state_machine(),
        "sla_rules": sla_rules,
    }


def _ticket_payload(category_id: UUID) -> TicketCreate:
    return TicketCreate(
        category_id=category_id,
        reporter_id="reporter-1",
        subject_id="subject-1",
        priority="normal",
        client_ticket_id=f"ticket-{uuid4().hex}",
        initial_message=TicketMessageAppendRequest(
            body_markdown="Initial",
            visibility="reporter_visible",
            client_message_id=f"message-{uuid4().hex}",
            author_actor_kind="user",
            author_actor_id="reporter-1",
        ),
        originating_actor_kind="user",
        originating_actor_id="reporter-1",
    )


def _create_ticket_with_sla(
    tickets_service: TicketsService,
    *,
    sla_rules: dict[str, Any],
) -> UUID:
    with use_audit_context(_audit_context()):
        category, _ = tickets_service.create_category(
            TicketCategoryCreate.model_validate(
                _category_payload(sla_rules=sla_rules)
            ),
            _actor(),
        )
        created, _ = tickets_service.create_ticket(
            _ticket_payload(category.id),
            ActorIdentity(actor_kind="service", actor_id="discord-ticket-bot"),
        )
    return created.ticket.id


def _age_ticket(dsn: str, ticket_id: UUID, *, created_at: datetime) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE tickets
            SET created_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (created_at, created_at, ticket_id),
        )


def _set_owner(dsn: str, ticket_id: UUID, owner_id: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "UPDATE tickets SET owner_id = %s WHERE id = %s",
            (owner_id, ticket_id),
        )


def _fetch_triggers(dsn: str, ticket_id: UUID) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT ticket_id, rule_key, threshold_seconds, consequence,
                   target_state, state, elapsed_seconds, effect_summary_json
            FROM ticket_sla_triggers
            WHERE ticket_id = %s
            ORDER BY applied_at ASC, id ASC
            """,
            (ticket_id,),
        ).fetchall()


def _fetch_events(dsn: str) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, event_type, scope_kind, scope_id, payload_json
            FROM notification_events
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()


def _fetch_ticket(dsn: str, ticket_id: UUID) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT id, state, owner_id
            FROM tickets
            WHERE id = %s
            """,
            (ticket_id,),
        ).fetchone()
    assert row is not None
    return row


def _fetch_transitions(dsn: str, ticket_id: UUID) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT action, from_state, to_state, actor_kind, actor_id, reason
            FROM ticket_transitions
            WHERE ticket_id = %s
            ORDER BY aggregate_seq ASC
            """,
            (ticket_id,),
        ).fetchall()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def ticket_services(
    governance_dsn: str,  # noqa: ARG001 — resets tables before resolving the app container
    ticket_app_with_overrides: tuple[Any, Any],
) -> tuple[TicketsService, TicketSlaService]:
    _app, container = ticket_app_with_overrides
    return container.services.tickets(), container.services.ticket_sla()


@pytest.fixture()
def tickets_service(
    ticket_services: tuple[TicketsService, TicketSlaService],
) -> TicketsService:
    tickets, _ticket_sla = ticket_services
    return tickets


@pytest.fixture()
def ticket_sla_service(
    ticket_services: tuple[TicketsService, TicketSlaService],
) -> TicketSlaService:
    _tickets, ticket_sla = ticket_services
    return ticket_sla


def test_thresholds_fire_ascending_without_skipping(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "owner",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 300, "consequence": "notify_scope"},
                        {"elapsed_seconds": 900, "consequence": "flag_for_review"},
                    ],
                },
                {
                    "key": "queue",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 600, "consequence": "notify_scope"},
                    ],
                },
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(seconds=1000))

    applied = ticket_sla_service.evaluate_ticket_sla(now=now)

    assert [(item.rule_key, item.threshold_seconds) for item in applied] == [
        ("owner", 300),
        ("queue", 600),
        ("owner", 900),
    ]
    persisted = [
        (row["rule_key"], int(row["threshold_seconds"]))
        for row in _fetch_triggers(governance_dsn, ticket_id)
    ]
    assert sorted(persisted, key=lambda item: item[1]) == [
        ("owner", 300),
        ("queue", 600),
        ("owner", 900),
    ]


def test_auto_escalate_reachable_target_transitions_ticket(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "open-escalation",
                    "states": ["open"],
                    "thresholds": [
                        {
                            "elapsed_seconds": 60,
                            "consequence": "auto_escalate",
                            "target_state": "triaged",
                        },
                        {"elapsed_seconds": 120, "consequence": "notify_scope"},
                    ],
                }
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    applied = ticket_sla_service.evaluate_ticket_sla(now=now)

    assert len(applied) == 1
    assert applied[0].consequence == "auto_escalate"
    assert applied[0].effect_summary["result"] == "transitioned"
    assert _fetch_events(governance_dsn) == []
    assert _fetch_ticket(governance_dsn, ticket_id)["state"] == "triaged"
    transitions = _fetch_transitions(governance_dsn, ticket_id)
    assert [(row["action"], row["to_state"]) for row in transitions] == [
        ("triage", "triaged")
    ]
    assert transitions[0]["actor_kind"] == "service"
    assert transitions[0]["actor_id"] == "sla-worker"


def test_auto_escalate_multihop_target_flags_for_review(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "too-old",
                    "states": ["open"],
                    "thresholds": [
                        {
                            "elapsed_seconds": 60,
                            "consequence": "auto_escalate",
                            "target_state": "closed",
                        }
                    ],
                }
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    applied = ticket_sla_service.evaluate_ticket_sla(now=now)

    assert len(applied) == 1
    assert applied[0].consequence == "auto_escalate"
    assert applied[0].effect_summary["result"] == "flag_for_review"
    assert applied[0].effect_summary["fallback_from"] == "auto_escalate"
    assert _fetch_ticket(governance_dsn, ticket_id)["state"] == "open"
    assert _fetch_transitions(governance_dsn, ticket_id) == []
    events = _fetch_events(governance_dsn)
    assert [row["event_type"] for row in events] == ["ticket.sla.flag_for_review"]
    assert events[0]["scope_kind"] == "chapter"
    assert events[0]["scope_id"] == "chapter-1"


def test_rerun_does_not_duplicate_triggers_events_or_transitions(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "notify",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 30, "consequence": "notify_scope"},
                    ],
                }
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    first = ticket_sla_service.evaluate_ticket_sla(now=now)
    second = ticket_sla_service.evaluate_ticket_sla(now=now + timedelta(minutes=1))

    assert len(first) == 1
    assert second == []
    assert len(_fetch_triggers(governance_dsn, ticket_id)) == 1
    assert len(_fetch_events(governance_dsn)) == 1
    assert _fetch_transitions(governance_dsn, ticket_id) == []


def test_notifications_are_published_through_notification_events_emit(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    ticket_app_with_overrides: tuple[Any, Any],
) -> None:
    _app, container = ticket_app_with_overrides
    tickets_service = container.services.tickets()
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "owner",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 30, "consequence": "notify_owner"},
                    ],
                }
            ],
        },
    )
    _set_owner(governance_dsn, ticket_id, "owner-1")
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    class SpyNotificationEventsService:
        def __init__(self, wrapped: Any) -> None:
            self.wrapped = wrapped
            self.calls: list[dict[str, Any]] = []

        def emit(
            self,
            connection: Any | None = None,
            *,
            event: NotificationEventDraft,
            actor: ActorIdentity,
            payload_allowlist: frozenset[str] | None = None,
        ) -> NotificationEventRead:
            self.calls.append(
                {
                    "connection": connection,
                    "event": event,
                    "actor": actor,
                    "payload_allowlist": payload_allowlist,
                }
            )
            return self.wrapped.emit(
                connection,
                event=event,
                actor=actor,
                payload_allowlist=payload_allowlist,
            )

    spy = SpyNotificationEventsService(container.services.notification_events())
    container.services.notification_events.override(providers.Object(spy))
    try:
        ticket_sla_service = container.services.ticket_sla()
        ticket_sla_service.evaluate_ticket_sla(now=now)
    finally:
        container.services.notification_events.reset_override()

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert isinstance(call["event"], NotificationEventDraft)
    assert call["event"].event_type == "ticket.sla.notify_owner"
    assert call["event"].scope_kind == "chapter"
    assert call["event"].scope_id == "chapter-1"
    assert call["actor"] == ActorIdentity(actor_kind="service", actor_id="sla-worker")
    assert call["payload_allowlist"] == SLA_NOTIFICATION_PAYLOAD_ALLOWLIST
    assert _fetch_events(governance_dsn)[0]["payload_json"]["owner_id"] == "owner-1"


def test_notify_owner_with_no_owner_records_fallback_summary(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "owner",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 30, "consequence": "notify_owner"},
                    ],
                }
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    applied = ticket_sla_service.evaluate_ticket_sla(now=now)

    assert len(applied) == 1
    assert applied[0].consequence == "notify_owner"
    assert applied[0].effect_summary["result"] == "flag_for_review"
    assert applied[0].effect_summary["fallback_from"] == "notify_owner"
    assert applied[0].effect_summary["fallback_reason"] == "missing_owner"
    assert "notification_event_id" in applied[0].effect_summary
    triggers = _fetch_triggers(governance_dsn, ticket_id)
    assert len(triggers) == 1
    assert triggers[0]["consequence"] == "notify_owner"
    assert triggers[0]["effect_summary_json"]["fallback_reason"] == "missing_owner"
    events = _fetch_events(governance_dsn)
    assert [row["event_type"] for row in events] == ["ticket.sla.flag_for_review"]
    assert events[0]["payload_json"]["consequence"] == "notify_owner"
    assert events[0]["payload_json"]["owner_id"] is None


def test_concurrent_auto_escalate_stale_version_skips_cycle(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    caplog: pytest.LogCaptureFixture,
    tickets_service: TicketsService,
    ticket_app_with_overrides: tuple[Any, Any],
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "open-escalation",
                    "states": ["open"],
                    "thresholds": [
                        {
                            "elapsed_seconds": 60,
                            "consequence": "auto_escalate",
                            "target_state": "triaged",
                        }
                    ],
                }
            ],
        },
    )
    _age_ticket(governance_dsn, ticket_id, created_at=now - timedelta(minutes=5))

    class FakeTicketsService:
        def _raise_stale(self, *_args: Any, **_kwargs: Any) -> Any:
            raise StaleMutationError(
                aggregate_type="ticket",
                aggregate_id=str(ticket_id),
                expected_version=1,
                current_version=2,
            )

        def transition_ticket(self, *_args: Any, **_kwargs: Any) -> Any:
            return self._raise_stale(*_args, **_kwargs)

        def _transition_ticket_on(self, *_args: Any, **_kwargs: Any) -> Any:
            return self._raise_stale(*_args, **_kwargs)

    _app, container = ticket_app_with_overrides
    container.services.tickets.override(providers.Object(FakeTicketsService()))
    try:
        ticket_sla_service = container.services.ticket_sla()
        with caplog.at_level(logging.INFO, logger="app.services.ticket_sla"):
            applied = ticket_sla_service.evaluate_ticket_sla(now=now)
    finally:
        container.services.tickets.reset_override()

    assert applied == []
    assert _fetch_triggers(governance_dsn, ticket_id) == []
    assert _fetch_events(governance_dsn) == []
    assert _fetch_ticket(governance_dsn, ticket_id)["state"] == "open"
    assert "ticket SLA auto-escalate skipped stale ticket version" in caplog.text


def test_latest_transition_to_current_state_sets_state_entered_at(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    tickets_service: TicketsService,
    ticket_sla_service: TicketSlaService,
) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    ticket_id = _create_ticket_with_sla(
        tickets_service,
        sla_rules={
            "schema_version": 1,
            "rules": [
                {
                    "key": "review",
                    "states": ["open"],
                    "thresholds": [
                        {"elapsed_seconds": 300, "consequence": "flag_for_review"},
                    ],
                }
            ],
        },
    )
    created_at = now - timedelta(hours=2)
    latest_state_entry = now - timedelta(seconds=100)
    _age_ticket(governance_dsn, ticket_id, created_at=created_at)
    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO ticket_transitions (
                id, ticket_id, aggregate_seq, action, from_state, to_state,
                actor_kind, actor_id, recorded_at
            )
            VALUES (%s, %s, 2, 'reopen', 'triaged', 'open', 'user', 'operator', %s)
            """,
            (uuid4(), ticket_id, latest_state_entry),
        )

    applied = ticket_sla_service.evaluate_ticket_sla(now=now)

    assert applied == []
    assert _fetch_triggers(governance_dsn, ticket_id) == []


def test_sla_worker_grant_seed_uses_exact_match_containment(
    fresh_migrated_postgres_db: str,
    repo_root: Path,
) -> None:
    migration_text = (
        repo_root / "migrations/versions/wu-037_ticket_sla_triggers.py"
    ).read_text()
    assert "permissions @>" in migration_text
    assert "permissions <@" in migration_text
    assert "expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP" in migration_text

    with psycopg.connect(fresh_migrated_postgres_db, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT grantee_id, scope_kind, scope_id, permissions
            FROM authority_grants
            WHERE grantee_id = 'sla-worker'
              AND revoked_at IS NULL
            ORDER BY created_at ASC
            """
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["scope_kind"] == "global"
    assert rows[0]["scope_id"] is None
    assert rows[0]["permissions"] == [
        "notification.deliver",
        "ticket.read",
        "ticket.transition",
    ]


def test_exact_match_seed_guard_does_not_accept_superset_grant(
    fresh_postgres_dsn: str,
    alembic_runner: Any,
) -> None:
    before = alembic_runner(fresh_postgres_dsn, "upgrade", "wu_025c_ticket_messages")
    assert before.returncode == 0, before.stderr
    with psycopg.connect(fresh_postgres_dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO authority_grants (
                id, grantee_id, scope_kind, scope_id, permissions,
                expires_at, revoked_at, revoked_by, revocation_reason,
                predecessor_grant_id
            )
            VALUES (
                %s, 'sla-worker', 'global', NULL, %s,
                NULL, NULL, NULL, NULL, NULL
            )
            """,
            (
                uuid4(),
                Jsonb(
                    [
                        "notification.deliver",
                        "ticket.read",
                        "ticket.transition",
                        "ticket.create",
                    ]
                ),
            ),
        )
    after = alembic_runner(fresh_postgres_dsn, "upgrade", "head")
    assert after.returncode == 0, after.stderr

    with psycopg.connect(fresh_postgres_dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT permissions
            FROM authority_grants
            WHERE grantee_id = 'sla-worker'
              AND revoked_at IS NULL
            ORDER BY created_at ASC
            """
        ).fetchall()

    assert len(rows) == 2
    assert [
        "notification.deliver",
        "ticket.read",
        "ticket.transition",
    ] in [row["permissions"] for row in rows]
