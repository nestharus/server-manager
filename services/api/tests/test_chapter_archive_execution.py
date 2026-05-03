from __future__ import annotations

from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority
from functools import partial

from app.repositories.deferred_effects import DeferredEffectsRepository
from app.services.deferred_effects import DeferredEffectsService
from app.services.mutations import mutate_entity
from app.tasks.archive import archive_worker_tick, configure_archive_worker

from .chapter_governance_helpers import (
    ACTOR_HEADERS,
    CHAPTERS_URL,
    audit_context,
    create_active_chapter,
    seed_member_form_application,
    seed_operator_and_archiver_grants,
    seed_ticket,
)


def _archive_rows(db: PostgresDatabase) -> list[dict[str, object]]:
    with db.connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, chapter_id, correlation_id, causation_id, archive_reason, status
                FROM chapter_archive_runs
                ORDER BY initiated_at ASC
                """
            ).fetchall()


def _archive_effects(
    db: PostgresDatabase, archive_run_id: UUID
) -> list[dict[str, object]]:
    with db.connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, effect_type, idempotency_key, payload_json, status,
                       precondition_state, correlation_id, causation_id
                FROM deferred_effects
                WHERE payload_json->>'archive_run_id' = %s
                ORDER BY created_at ASC, id ASC
                """,
                (str(archive_run_id),),
            ).fetchall()


def test_archive_execute_is_idempotent_and_preserves_correlation_chain(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4/D15: archive execute is duplicate-safe and tags all effects with one chain."""
    configure_archive_worker(db=governance_db)
    seed_operator_and_archiver_grants(governance_db)
    chapter, etag = create_active_chapter(client)
    chapter_id = str(chapter["id"])
    application_id = seed_member_form_application(governance_db, chapter_id=chapter_id)
    ticket_id = seed_ticket(governance_db, chapter_id=chapter_id)
    with use_audit_context(audit_context()):
        grant = grant_authority(
            governance_db,
            grantee_id="chapter-officer",
            scope_kind="chapter",
            scope_id=chapter_id,
            permissions=frozenset({"ticket.transition"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )

    correlation_id = uuid4()
    causation_id = uuid4()
    response = client.post(
        f"{CHAPTERS_URL}/{chapter_id}/archive-execute",
        json={"archive_reason": "chapter retired"},
        headers={
            **ACTOR_HEADERS,
            "If-Match": etag,
            "X-Correlation-Id": str(correlation_id),
            "X-Causation-Id": str(causation_id),
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["chapter_state"] == "archiving"

    rows = _archive_rows(governance_db)
    assert len(rows) == 1
    archive_run = rows[0]
    assert archive_run["correlation_id"] == correlation_id
    assert archive_run["causation_id"] == causation_id
    effects = _archive_effects(governance_db, archive_run["id"])
    assert {effect["payload_json"]["target_id"] for effect in effects} == {
        application_id,
        ticket_id,
        str(grant.id),
    }
    assert {effect["correlation_id"] for effect in effects} == {correlation_id}
    assert {effect["causation_id"] for effect in effects} == {causation_id}
    for effect in effects:
        payload = effect["payload_json"]
        assert effect["idempotency_key"] == (
            f"chapter_archive:{archive_run['id']}:{payload['target_kind']}:"
            f"{payload['target_id']}:v{payload['expected_version']}"
        )

    duplicate = client.post(
        f"{CHAPTERS_URL}/{chapter_id}/archive-execute",
        json={"archive_reason": "chapter retired"},
        headers={
            **ACTOR_HEADERS,
            "If-Match": response.headers["etag"],
            "X-Correlation-Id": str(uuid4()),
        },
    )
    assert duplicate.status_code == HTTPStatus.CONFLICT
    assert duplicate.json()["code"] == "chapter_archive_in_progress"
    assert len(_archive_effects(governance_db, archive_run["id"])) == 3


def test_archive_worker_regenerates_stale_effects_and_finalizes_when_clear(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2/AC4: stale effects are replaced and archive finalizes only after work is done."""
    configure_archive_worker(db=governance_db)
    seed_operator_and_archiver_grants(governance_db)
    chapter, etag = create_active_chapter(client)
    chapter_id = str(chapter["id"])
    application_id = seed_member_form_application(governance_db, chapter_id=chapter_id)
    seed_ticket(governance_db, chapter_id=chapter_id)
    with use_audit_context(audit_context()):
        grant_authority(
            governance_db,
            grantee_id="chapter-officer",
            scope_kind="chapter",
            scope_id=chapter_id,
            permissions=frozenset({"ticket.transition"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )

    execute = client.post(
        f"{CHAPTERS_URL}/{chapter_id}/archive-execute",
        json={"archive_reason": "chapter retired"},
        headers={**ACTOR_HEADERS, "If-Match": etag, "X-Correlation-Id": str(uuid4())},
    )
    assert execute.status_code == HTTPStatus.OK, execute.text
    archive_run_id = UUID(execute.json()["archive_run_id"])
    with governance_db.connection() as connection:
        connection.execute(
            """
            UPDATE aggregate_heads
            SET current_seq = current_seq + 1
            WHERE aggregate_type = 'application'
              AND aggregate_id = %s
            """,
            (application_id,),
        )

    archive_worker_tick()
    effects_after_validation = _archive_effects(governance_db, archive_run_id)
    assert any(
        effect["payload_json"]["target_id"] == application_id
        and effect["status"] == "skipped"
        and effect["payload_json"]["expected_version"] == 2
        for effect in effects_after_validation
    )
    assert any(
        effect["payload_json"]["target_id"] == application_id
        and effect["payload_json"]["expected_version"] == 3
        for effect in effects_after_validation
    )

    DeferredEffectsService(
        deferred_effects_repo=DeferredEffectsRepository(governance_db),
        mutations_callable=partial(mutate_entity, db=governance_db),
    ).deferred_effect_worker_tick(worker_id="archive-test")
    archive_worker_tick()
    DeferredEffectsService(
        deferred_effects_repo=DeferredEffectsRepository(governance_db),
        mutations_callable=partial(mutate_entity, db=governance_db),
    ).deferred_effect_worker_tick(worker_id="archive-test")
    archive_worker_tick()

    status = client.get(
        f"{CHAPTERS_URL}/{chapter_id}/archive-status",
        headers=ACTOR_HEADERS,
    )
    assert status.status_code == HTTPStatus.OK, status.text
    assert status.json()["chapter_state"] == "archived"
    assert status.json()["status"] == "completed"


def test_archive_execute_rejects_invalid_start_state(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: archive execute rejects chapters that are not active or probation."""
    seed_operator_and_archiver_grants(governance_db)
    chapter, etag = create_active_chapter(client)
    archive = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "archive",
            "to_state": "archiving",
            "reason": "manual archive",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert archive.status_code == HTTPStatus.OK, archive.text

    execute = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/archive-execute",
        json={"archive_reason": "already archiving"},
        headers={**ACTOR_HEADERS, "If-Match": archive.headers["etag"]},
    )
    assert execute.status_code == HTTPStatus.CONFLICT
    assert execute.json()["code"] == "chapter_archive_prerequisites_blocked"
