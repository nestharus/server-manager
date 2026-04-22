from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.read_models import OperationalOverviewRead
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.read_models import (
    ACTIVE_DRIFT_STATUSES,
    OPEN_APPLICATION_STATES,
    OPERATIONAL_OVERVIEW_PROJECTION_NAME,
    PENDING_DEFERRED_EFFECT_STATUSES,
    STALE_EVENT_THRESHOLD,
    STALE_TIME_THRESHOLD,
    InvalidScopeError,
    read_operational_overview,
)


OVERVIEW_URL = "/api/v1/operations/overview"


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


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id}


def _grant(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
    scope_kind: str = "global",
    scope_id: str | None = None,
) -> None:
    from app.core.context import use_audit_context

    with use_audit_context(_audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _seed_member(conn: psycopg.Connection[Any], *, discord_user_id: str) -> UUID:
    member_id = uuid4()
    conn.execute(
        """
        INSERT INTO members (id, discord_user_id, joined_at, status)
        VALUES (%s, %s, %s, 'active')
        """,
        (member_id, discord_user_id, datetime.now(tz=UTC)),
    )
    return member_id


def _seed_form_definition(conn: psycopg.Connection[Any]) -> UUID:
    form_id = uuid4()
    form_scope_id = f"form-{uuid4().hex[:8]}"
    conn.execute(
        """
        INSERT INTO form_definitions (
            id,
            scope_kind,
            scope_id,
            version,
            name,
            target_type,
            fields,
            routing_rules,
            status,
            published_by_kind,
            published_by_id,
            published_at
        )
        VALUES (
            %s, %s, %s, 1, %s, 'custom', %s, %s, 'current', 'user', 'operator', %s
        )
        """,
        (
            form_id,
            "member",
            form_scope_id,
            f"Form-{uuid4().hex[:8]}",
            Jsonb([]),
            Jsonb({"schema_version": 1, "queue": "chapter_officers"}),
            datetime.now(tz=UTC),
        ),
    )
    return form_id


def _seed_application_row(
    database_url: str,
    *,
    state: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        applicant_id = _seed_member(conn, discord_user_id=f"applicant-{uuid4().hex[:8]}")
        form_id = _seed_form_definition(conn)
        owner_id: UUID | None = None
        if state in {"claimed", "in_review", "interview", "waitlisted"}:
            owner_id = _seed_member(conn, discord_user_id=f"owner-{uuid4().hex[:8]}")
        now = datetime.now(tz=UTC)
        conn.execute(
            """
            INSERT INTO applications (
                id,
                applicant_id,
                form_definition_id,
                form_version,
                form_snapshot,
                target_scope_kind,
                target_scope_id,
                responses,
                state,
                owner_id,
                interview_thread_id,
                decision_reason,
                client_application_id,
                submitted_at,
                queued_at,
                claimed_at,
                review_started_at,
                decided_at,
                withdrawn_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s
            )
            """,
            (
                uuid4(),
                applicant_id,
                form_id,
                Jsonb({"form_version": 1}),
                scope_kind,
                scope_id,
                Jsonb({"field": "value"}),
                state,
                owner_id,
                None if state != "interview" else f"thread-{uuid4().hex[:6]}",
                "decision recorded" if state in {"approved", "denied"} else None,
                f"client-{uuid4().hex[:8]}",
                now,
                now if state != "submitted" else None,
                now if state in {"claimed", "in_review", "interview", "waitlisted"} else None,
                now if state in {"in_review", "interview", "waitlisted"} else None,
                now,
                now,
            ),
        )


def _seed_ticket_row(
    database_url: str,
    *,
    scope_kind: str,
    scope_id: str | None,
    terminal: bool,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        category_id = uuid4()
        state = "closed" if terminal else "open"
        now = datetime.now(tz=UTC)
        conn.execute(
            """
            INSERT INTO ticket_categories (
                id,
                name,
                routing_scope,
                privacy_level,
                state_machine,
                sla_rules
            )
            VALUES (%s, %s, %s, 'reporter_staff', %s, %s)
            """,
            (
                category_id,
                f"Category-{uuid4().hex[:8]}",
                Jsonb(
                    {
                        "scope_kind": scope_kind,
                        "scope_id": scope_id,
                        "queue": "officers",
                    }
                ),
                Jsonb({"schema_version": 1, "initial_state": "open", "states": [], "edges": []}),
                Jsonb({"schema_version": 1, "rules": []}),
            ),
        )
        conn.execute(
            """
            INSERT INTO tickets (
                id,
                category_id,
                category_version,
                category_snapshot,
                reporter_id,
                subject_id,
                state,
                priority,
                owner_id,
                resolution,
                client_ticket_id,
                terminal_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, 1, %s, %s, NULL, %s, 'normal', NULL, NULL, %s, %s, %s, %s
            )
            """,
            (
                uuid4(),
                category_id,
                Jsonb(
                    {
                        "routing_scope": {
                            "scope_kind": scope_kind,
                            "scope_id": scope_id,
                            "queue": "officers",
                        }
                    }
                ),
                f"reporter-{uuid4().hex[:6]}",
                state,
                f"client-{uuid4().hex[:8]}",
                now if terminal else None,
                now,
                now,
            ),
        )


def _seed_permission_drift_row(
    database_url: str,
    *,
    status: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO permission_drift (
                id,
                permission_intent_id,
                intent_version,
                actual_bits,
                actual_allow_bits,
                actual_deny_bits,
                intended_bits,
                intended_allow_bits,
                intended_deny_bits,
                status,
                detected_at,
                scope_kind,
                scope_id,
                role_id,
                channel_id,
                kind,
                reconciliation_run_id,
                resolved_by_kind,
                resolved_by_id,
                resolved_at,
                resolution_reason
            )
            VALUES (
                %s, NULL, NULL, 1, NULL, NULL, 2, NULL, NULL, %s, %s, %s, %s, %s, NULL,
                'guild_role', NULL, %s, %s, %s, %s
            )
            """,
            (
                uuid4(),
                status,
                datetime.now(tz=UTC),
                scope_kind,
                scope_id,
                f"role-{uuid4().hex[:8]}",
                None if status == "detected" else "system",
                None if status == "detected" else "resolver",
                None if status == "detected" else datetime.now(tz=UTC),
                None if status == "detected" else "resolved",
            ),
        )


def _seed_deferred_effect_row(database_url: str, *, status: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        now = datetime.now(tz=UTC)
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
                causation_id,
                created_at,
                updated_at
            )
            VALUES (
                %s, 'operations', 'refresh', %s, %s, 'safe', 'valid', %s,
                NULL, NULL, NULL, 0, 3, NULL, %s, NULL, %s, %s
            )
            """,
            (
                uuid4(),
                f"idem-{uuid4().hex}",
                Jsonb({"kind": "refresh"}),
                status,
                uuid4(),
                now,
                now,
            ),
        )


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
                'test:operations',
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


def _set_cursor(
    database_url: str,
    *,
    last_processed_id: int,
    last_processed_at: datetime | None,
    version: int,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE read_model_cursors
            SET last_processed_id = %s,
                last_processed_at = %s,
                version = %s
            WHERE projection_name = %s
            """,
            (
                last_processed_id,
                last_processed_at,
                version,
                OPERATIONAL_OVERVIEW_PROJECTION_NAME,
            ),
        )


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


@pytest.mark.asyncio
async def test_global_overview_returns_counts_from_projections(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: global overview counts only the whitelisted projection predicates."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    for state in sorted(OPEN_APPLICATION_STATES):
        _seed_application_row(governance_dsn, state=state, scope_kind="chapter", scope_id="chapter-a")
    _seed_application_row(governance_dsn, state="approved", scope_kind="chapter", scope_id="chapter-a")
    _seed_ticket_row(governance_dsn, scope_kind="chapter", scope_id="chapter-a", terminal=False)
    _seed_ticket_row(governance_dsn, scope_kind="chapter", scope_id="chapter-a", terminal=False)
    _seed_ticket_row(governance_dsn, scope_kind="chapter", scope_id="chapter-a", terminal=True)
    for status in sorted(PENDING_DEFERRED_EFFECT_STATUSES):
        _seed_deferred_effect_row(governance_dsn, status=status)
    _seed_deferred_effect_row(governance_dsn, status="completed")
    _seed_deferred_effect_row(governance_dsn, status="skipped")
    for status in sorted(ACTIVE_DRIFT_STATUSES):
        _seed_permission_drift_row(
            governance_dsn,
            status=status,
            scope_kind="chapter",
            scope_id="chapter-a",
        )
    _seed_permission_drift_row(
        governance_dsn,
        status="accepted",
        scope_kind="chapter",
        scope_id="chapter-a",
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["open_applications_count"] == len(OPEN_APPLICATION_STATES)
    assert body["open_tickets_count"] == 2
    assert body["pending_deferred_effects_count"] == len(PENDING_DEFERRED_EFFECT_STATUSES)
    assert body["permission_drift_count"] == len(ACTIVE_DRIFT_STATUSES)


@pytest.mark.asyncio
async def test_chapter_overview_filters_counts_to_chapter(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: chapter overview filters applications, tickets, and drift to the requested chapter."""
    _grant(
        governance_db,
        actor_id="chapter-operator",
        permissions=frozenset({"operational_overview.read"}),
        scope_kind="chapter",
        scope_id="chapter-a",
    )
    _seed_application_row(governance_dsn, state="queued", scope_kind="chapter", scope_id="chapter-a")
    _seed_application_row(governance_dsn, state="queued", scope_kind="chapter", scope_id="chapter-b")
    _seed_application_row(governance_dsn, state="queued", scope_kind="global", scope_id=None)
    _seed_ticket_row(governance_dsn, scope_kind="chapter", scope_id="chapter-a", terminal=False)
    _seed_ticket_row(governance_dsn, scope_kind="chapter", scope_id="chapter-b", terminal=False)
    _seed_ticket_row(governance_dsn, scope_kind="global", scope_id=None, terminal=False)
    _seed_permission_drift_row(
        governance_dsn,
        status="detected",
        scope_kind="chapter",
        scope_id="chapter-a",
    )
    _seed_permission_drift_row(
        governance_dsn,
        status="detected",
        scope_kind="chapter",
        scope_id="chapter-b",
    )
    _seed_permission_drift_row(
        governance_dsn,
        status="detected",
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-a"},
        headers=_headers("chapter-operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["open_applications_count"] == 1
    assert body["open_tickets_count"] == 1
    assert body["permission_drift_count"] == 1


@pytest.mark.asyncio
async def test_chapter_overview_deferred_effects_count_is_zero(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: chapter overview reports zero deferred effects because that table has no first-class chapter scope."""
    _grant(
        governance_db,
        actor_id="chapter-operator",
        permissions=frozenset({"operational_overview.read"}),
        scope_kind="chapter",
        scope_id="chapter-a",
    )
    for status in sorted(PENDING_DEFERRED_EFFECT_STATUSES):
        _seed_deferred_effect_row(governance_dsn, status=status)

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-a"},
        headers=_headers("chapter-operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["pending_deferred_effects_count"] == 0


@pytest.mark.asyncio
async def test_overview_stale_when_lag_exceeds_event_threshold(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: overview is stale when cursor lag exceeds the event threshold."""
    monkeypatch.setattr("app.services.read_models.STALE_EVENT_THRESHOLD", 1)
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    _append_state_change(governance_dsn, recorded_at=datetime.now(tz=UTC) - timedelta(seconds=10))
    _append_state_change(governance_dsn, recorded_at=datetime.now(tz=UTC) - timedelta(seconds=9))

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is True
    assert body["stale_projections"] == [OPERATIONAL_OVERVIEW_PROJECTION_NAME]
    assert body["stale_since"] is None


@pytest.mark.asyncio
async def test_overview_stale_when_last_processed_at_exceeds_time_threshold(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: overview is stale when the cursor timestamp is old AND settled events remain unprocessed."""
    monkeypatch.setattr("app.services.read_models.STALE_TIME_THRESHOLD", timedelta(minutes=5))
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    _append_state_change(governance_dsn, recorded_at=datetime.now(tz=UTC) - timedelta(seconds=30))
    last_processed_at = datetime.now(tz=UTC) - timedelta(minutes=10)
    _set_cursor(
        governance_dsn,
        last_processed_id=0,
        last_processed_at=last_processed_at,
        version=1,
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is True
    assert body["stale_projections"] == [OPERATIONAL_OVERVIEW_PROJECTION_NAME]
    assert datetime.fromisoformat(body["stale_since"].replace("Z", "+00:00")) == last_processed_at


@pytest.mark.asyncio
async def test_cursor_caught_up_not_stale_despite_idle_time(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC4 (regression): a fully caught-up cursor stays fresh even when last_processed_at is old."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    idle_last_processed_at = datetime.now(tz=UTC) - timedelta(minutes=10)
    _set_cursor(
        governance_dsn,
        last_processed_id=0,
        last_processed_at=idle_last_processed_at,
        version=1,
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is False
    assert body["stale_projections"] == []
    assert body["stale_since"] is None


@pytest.mark.asyncio
async def test_stale_signal_does_not_flag_healthy_projector_under_load(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC4 (regression): reader uses the same MIN_AGE_SECONDS fence as the worker so within-fence writes don't look like lag."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    now_ts = datetime.now(tz=UTC)
    _append_state_change(governance_dsn, recorded_at=now_ts)
    _append_state_change(governance_dsn, recorded_at=now_ts)
    last_processed_at = now_ts - timedelta(minutes=10)
    _set_cursor(
        governance_dsn,
        last_processed_id=0,
        last_processed_at=last_processed_at,
        version=1,
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is False
    assert body["stale_projections"] == []
    assert body["stale_since"] is None


@pytest.mark.asyncio
async def test_overview_fresh_stream_is_not_stale(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC4: overview is fresh when lag is zero and the cursor timestamp is recent."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    event_id = _append_state_change(governance_dsn, recorded_at=datetime.now(tz=UTC) - timedelta(seconds=10))
    _set_cursor(
        governance_dsn,
        last_processed_id=event_id,
        last_processed_at=datetime.now(tz=UTC),
        version=1,
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is False
    assert body["stale_projections"] == []
    assert body["stale_since"] is None


@pytest.mark.asyncio
async def test_overview_empty_stream_never_advanced_is_not_stale(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: empty stream plus never-advanced cursor stays fresh."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["is_stale"] is False
    assert body["stale_projections"] == []
    assert body["stale_since"] is None


@pytest.mark.asyncio
async def test_overview_rejects_unauthorized_caller_with_403(
    migrated_async_client: AsyncClient,
) -> None:
    """AC4: unauthorized callers receive 403 for the overview read."""
    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("unauthorized"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "authority_decision_denied"


@pytest.mark.asyncio
async def test_overview_rejects_chapter_scope_without_scope_id_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: endpoint rejects chapter scope requests that omit scope_id."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "chapter"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["message"] == "scope_id is required when scope_kind='chapter'"


@pytest.mark.asyncio
async def test_overview_rejects_global_scope_with_scope_id_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: endpoint rejects global scope requests that include scope_id."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global", "scope_id": "chapter-a"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["message"] == "scope_id must be omitted when scope_kind='global'"


@pytest.mark.asyncio
async def test_overview_response_shape_matches_contract(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: overview response matches the OperationalOverviewRead contract exactly."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    model = OperationalOverviewRead.model_validate(payload)
    assert set(payload) == set(OperationalOverviewRead.model_fields)
    assert model.scope_kind == "global"


def test_service_rejects_chapter_scope_without_scope_id(
    governance_db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: service rejects malformed chapter scope before authority evaluation."""

    def _unexpected(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("authority evaluation must not run for invalid scope shape")

    monkeypatch.setattr("app.services.read_models._require_scoped_authority", _unexpected)

    with pytest.raises(InvalidScopeError) as exc_info:
        read_operational_overview(
            governance_db,
            scope_kind="chapter",
            scope_id=None,
            actor=ActorIdentity(actor_kind="user", actor_id="operator"),
            now=datetime.now(tz=UTC),
        )

    assert str(exc_info.value) == "scope_id is required when scope_kind='chapter'"


def test_service_rejects_global_scope_with_scope_id(
    governance_db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: service rejects malformed global scope before authority evaluation."""

    def _unexpected(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("authority evaluation must not run for invalid scope shape")

    monkeypatch.setattr("app.services.read_models._require_scoped_authority", _unexpected)

    with pytest.raises(InvalidScopeError) as exc_info:
        read_operational_overview(
            governance_db,
            scope_kind="global",
            scope_id="chapter-a",
            actor=ActorIdentity(actor_kind="user", actor_id="operator"),
            now=datetime.now(tz=UTC),
        )

    assert str(exc_info.value) == "scope_id must be omitted when scope_kind='global'"


@pytest.mark.asyncio
async def test_overview_returns_503_when_cursor_not_seeded(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC4: endpoint surfaces missing cursor seed as 503 instead of 500 or silent empty data."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"operational_overview.read"}),
    )
    _delete_cursor(governance_dsn)

    response = await migrated_async_client.get(
        OVERVIEW_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, response.text
    assert response.json()["code"] == "projection_not_initialized"
    assert OPERATIONAL_OVERVIEW_PROJECTION_NAME in response.json()["message"]


def test_operational_view_threshold_constants_are_module_level() -> None:
    """AC4: staleness thresholds remain importable module-level constants for tests and runtime wiring."""
    assert isinstance(STALE_EVENT_THRESHOLD, int) and STALE_EVENT_THRESHOLD > 0
    assert STALE_TIME_THRESHOLD > timedelta(0)
