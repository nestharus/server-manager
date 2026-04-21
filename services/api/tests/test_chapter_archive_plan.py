from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.contracts.scheduler import DeferredEffectCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.deferred_effects import enqueue_effect

from .chapter_governance_helpers import (
    ACTOR_HEADERS,
    CHAPTERS_URL,
    audit_context,
    create_active_chapter,
    seed_member_form_application,
    seed_operator_and_archiver_grants,
    seed_ticket,
)


def _table_counts(db: PostgresDatabase) -> dict[str, int]:
    with db.connection() as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "activity_actions",
                "activity_state_changes",
                "chapter_archive_runs",
                "chapter_transitions",
                "deferred_effects",
            )
        }


def test_archive_plan_enumerates_pending_work_without_mutating(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: archive plan lists pending work and does not mutate any subsystem."""
    seed_operator_and_archiver_grants(governance_db)
    chapter, _etag = create_active_chapter(client)
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
        effect = enqueue_effect(
            governance_db,
            DeferredEffectCreate(
                subsystem="chapter_provisioning",
                effect_type="chapter_provisioning_retry",
                idempotency_key=f"plan-test:{uuid4()}",
                payload_json={"chapter_id": chapter_id},
                consequence_level="safe",
            ),
        )

    role_id = uuid4()
    member_id = uuid4()
    roster_id = uuid4()
    with governance_db.connection() as connection:
        connection.execute(
            """
            INSERT INTO chapter_roles (
                id, chapter_id, template_id, name, ordinal, triggers_succession
            )
            VALUES (%s, %s, NULL, 'member', 10, false)
            """,
            (role_id, chapter_id),
        )
        connection.execute(
            """
            INSERT INTO members (id, discord_user_id, joined_at, status)
            VALUES (%s, %s, CURRENT_TIMESTAMP, 'active')
            """,
            (member_id, f"discord-{member_id}"),
        )
        connection.execute(
            """
            INSERT INTO roster_entries (
                id, chapter_id, member_id, role_id, status, removal_metadata
            )
            VALUES (%s, %s, %s, %s, 'active', %s)
            """,
            (roster_id, chapter_id, member_id, role_id, Jsonb({})),
        )

    before = _table_counts(governance_db)
    response = client.get(
        f"{CHAPTERS_URL}/{chapter_id}/archive-plan",
        headers=ACTOR_HEADERS,
    )
    after = _table_counts(governance_db)

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["pending_applications"]["count"] == 1
    assert body["pending_applications"]["sample_ids"] == [application_id]
    assert body["open_tickets"]["count"] == 1
    assert body["open_tickets"]["sample_ids"] == [ticket_id]
    assert body["active_authority_grants"]["count"] == 1
    assert body["active_authority_grants"]["sample_ids"] == [str(grant.id)]
    assert body["unresolved_deferred_effects"]["count"] == 1
    assert body["unresolved_deferred_effects"]["sample_ids"] == [str(effect.id)]
    assert body["active_roster_entries"]["count"] == 1
    assert body["chapter_roles"]["count"] == 1
    assert body["discord_resources"] == chapter["discord_resources"]
    assert after == before
