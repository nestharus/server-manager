from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.chapter_templates import CURRENT_TEMPLATE_SCHEMA_VERSION
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


ACTOR_HEADERS = {"X-Actor-Kind": "user", "X-Actor-Id": "operator"}
TEMPLATES_URL = "/api/v1/chapter-templates"
CHAPTERS_URL = "/api/v1/chapters"


def audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def seed_operator_and_archiver_grants(db: PostgresDatabase) -> None:
    with use_audit_context(audit_context()):
        grant_authority(
            db,
            grantee_id="operator",
            scope_kind="global",
            scope_id=None,
            permissions=frozenset(
                {
                    "chapter_template.read",
                    "chapter_template.write",
                    "chapter.read",
                    "chapter.write",
                }
            ),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )
        grant_authority(
            db,
            grantee_id="operator",
            scope_kind="chapter",
            scope_id=None,
            permissions=frozenset(
                {
                    "chapter.archive",
                    "chapter.archive_plan.read",
                    "chapter.governance",
                }
            ),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )
        grant_authority(
            db,
            grantee_id="chapter-archiver",
            scope_kind="chapter",
            scope_id=None,
            permissions=frozenset(
                {
                    "application.withdraw",
                    "authority.revoke",
                    "ticket.transition",
                }
            ),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def template_payload() -> dict[str, object]:
    return {
        "name": f"Starter Chapter {uuid4()}",
        "schema_version": CURRENT_TEMPLATE_SCHEMA_VERSION,
        "channel_structure": [
            {"name": "announcements", "type": "text", "topic": "Chapter news"},
            {"name": "general", "type": "text"},
        ],
        "role_structure": [
            {"name": "officer", "ordinal": 10, "triggers_succession": True},
            {"name": "member", "ordinal": 20, "triggers_succession": False},
        ],
        "default_permission_intents": [],
    }


def ready_resources() -> dict[str, object]:
    return {
        "category_id": "cat-1",
        "role_ids": {"officer": "role-1", "member": "role-2"},
        "channel_ids": {"announcements": "chan-1", "general": "chan-2"},
    }


def create_active_chapter(client: TestClient) -> tuple[dict[str, object], str]:
    template_response = client.post(
        TEMPLATES_URL,
        json=template_payload(),
        headers=ACTOR_HEADERS,
    )
    assert template_response.status_code == HTTPStatus.CREATED, template_response.text
    template = template_response.json()
    create_response = client.post(
        CHAPTERS_URL,
        json={
            "name": f"Humility {uuid4()}",
            "template_id": template["id"],
            "configuration": {},
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers=ACTOR_HEADERS,
    )
    assert create_response.status_code == HTTPStatus.CREATED, create_response.text
    chapter = create_response.json()
    etag = create_response.headers["etag"]
    provisioning = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/transitions",
        json={
            "to_state": "provisioning",
            "reason": "provision",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert provisioning.status_code == HTTPStatus.OK, provisioning.text
    etag = provisioning.headers["etag"]
    resources = client.patch(
        f"{CHAPTERS_URL}/{chapter['id']}/discord-resources",
        json={"resources": ready_resources()},
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert resources.status_code == HTTPStatus.OK, resources.text
    etag = resources.headers["etag"]
    active = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/transitions",
        json={
            "to_state": "active",
            "reason": "ready",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert active.status_code == HTTPStatus.OK, active.text
    return active.json(), active.headers["etag"]


def insert_aggregate_head(
    db: PostgresDatabase,
    *,
    aggregate_type: str,
    aggregate_id: str,
    version: int,
) -> None:
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type,
                aggregate_id,
                current_seq,
                latest_change_id
            )
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (aggregate_type, aggregate_id)
            DO UPDATE SET current_seq = EXCLUDED.current_seq
            """,
            (aggregate_type, aggregate_id, version),
        )


def seed_member_form_application(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    state: str = "queued",
) -> str:
    member_id = uuid4()
    form_id = uuid4()
    application_id = uuid4()
    now = datetime.now(UTC)
    form_snapshot = {
        "schema_version": 1,
        "form_definition_id": str(form_id),
        "name": "Chapter Intake",
        "target_type": "chapter_membership",
        "scope_kind": "chapter",
        "scope_id": chapter_id,
        "form_version": 1,
        "target_scope": {"scope_kind": "chapter", "scope_id": chapter_id},
        "fields": [],
        "routing_rules": {"schema_version": 1, "queue": "chapter_officers"},
    }
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO members (id, discord_user_id, joined_at, status, kind)
            VALUES (%s, %s, %s, 'active', 'discord')
            """,
            (member_id, f"discord-{member_id}", now),
        )
        connection.execute(
            """
            INSERT INTO form_definitions (
                id, scope_kind, scope_id, version, name, target_type, fields,
                routing_rules, status, published_by_kind, published_by_id
            )
            VALUES (%s, 'chapter', %s, 1, 'Chapter Intake', 'chapter_membership',
                    '[]'::jsonb, %s, 'current', 'user', 'operator')
            """,
            (
                form_id,
                chapter_id,
                Jsonb({
                    "schema_version": 1,
                    "queue": "chapter_officers",
                }),
            ),
        )
        connection.execute(
            """
            INSERT INTO applications (
                id, applicant_id, form_definition_id, form_version, form_snapshot,
                target_scope_kind, target_scope_id, responses, state, owner_id,
                decision_reason, client_application_id, submitted_at, queued_at,
                claimed_at, review_started_at, decided_at, withdrawn_at
            )
            VALUES (%s, %s, %s, 1, %s, 'chapter', %s, '{}'::jsonb, %s, NULL,
                    NULL, NULL, %s, %s, NULL, NULL, NULL, NULL)
            """,
            (
                application_id,
                member_id,
                form_id,
                Jsonb(form_snapshot),
                chapter_id,
                state,
                now,
                now,
            ),
        )
    insert_aggregate_head(
        db,
        aggregate_type="member",
        aggregate_id=str(member_id),
        version=1,
    )
    insert_aggregate_head(
        db,
        aggregate_type="application",
        aggregate_id=str(application_id),
        version=2,
    )
    return str(application_id)


def ticket_state_machine(*, closable: bool = True) -> dict[str, object]:
    edges = []
    if closable:
        edges.append(
            {
                "from": "open",
                "to": "closed",
                "action": "close",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            }
        )
    return {
        "schema_version": 1,
        "initial_state": "open",
        "states": [
            {"key": "open", "label": "Open", "terminal": False},
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": edges,
    }


def seed_ticket(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    closable: bool = True,
) -> str:
    category_id = uuid4()
    ticket_id = uuid4()
    snapshot = {
        "schema_version": 1,
        "category_id": str(category_id),
        "name": f"Chapter Tickets {category_id}",
        "category_version": 1,
        "routing_scope": {
            "scope_kind": "chapter",
            "scope_id": chapter_id,
            "queue": "chapter_officers",
        },
        "privacy_level": "staff_only",
        "state_machine": ticket_state_machine(closable=closable),
        "sla_rules": {"schema_version": 1, "rules": []},
    }
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO ticket_categories (
                id, name, routing_scope, privacy_level, state_machine, sla_rules
            )
            VALUES (%s, %s, %s, 'staff_only', %s, '{"schema_version": 1, "rules": []}'::jsonb)
            """,
            (
                category_id,
                f"Chapter Tickets {category_id}",
                Jsonb(snapshot["routing_scope"]),
                Jsonb(snapshot["state_machine"]),
            ),
        )
        connection.execute(
            """
            INSERT INTO tickets (
                id, category_id, category_version, category_snapshot, reporter_id,
                subject_id, state, priority, owner_id, resolution,
                client_ticket_id, terminal_at
            )
            VALUES (%s, %s, 1, %s, 'reporter', NULL, 'open', 'normal',
                    NULL, NULL, NULL, NULL)
            """,
            (ticket_id, category_id, Jsonb(snapshot)),
        )
    insert_aggregate_head(
        db,
        aggregate_type="ticket",
        aggregate_id=str(ticket_id),
        version=1,
    )
    return str(ticket_id)
