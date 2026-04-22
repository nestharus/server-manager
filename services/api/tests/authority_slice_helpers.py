from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.members import create_or_get_member


def actor_headers(*, actor_id: str, actor_kind: str = "user") -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


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


def create_member(db: PostgresDatabase, *, discord_user_id: str) -> str:
    with use_audit_context(audit_context()):
        member, _result, _created = create_or_get_member(
            db,
            MemberCreate(
                discord_user_id=discord_user_id,
                joined_at=datetime.now(UTC),
                originating_actor_kind="user",
                originating_actor_id=discord_user_id,
            ),
            ActorIdentity(actor_kind="user", actor_id=discord_user_id),
        )
    return str(member.id)


def grant_permission(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    with use_audit_context(audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=frozenset({permission}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def ensure_chapter(db: PostgresDatabase, *, chapter_id: str) -> None:
    with db.connection() as connection:
        existing = connection.execute(
            "SELECT 1 FROM chapters WHERE id = %s",
            (chapter_id,),
        ).fetchone()
        if existing is not None:
            return
        template_id = uuid4()
        connection.execute(
            """
            INSERT INTO chapter_templates (
                id,
                template_family_id,
                version,
                name,
                schema_version,
                channel_structure,
                role_structure,
                default_permission_intents
            )
            VALUES (%s, %s, 1, %s, 1, '[]'::jsonb, %s, '[]'::jsonb)
            """,
            (
                template_id,
                template_id,
                f"Template {chapter_id}",
                Jsonb(
                    [
                        {"name": "member", "ordinal": 10, "triggers_succession": False},
                        {"name": "officer", "ordinal": 20, "triggers_succession": True},
                    ]
                ),
            ),
        )
        connection.execute(
            """
            INSERT INTO chapters (
                id,
                name,
                template_id,
                template_snapshot,
                configuration,
                state,
                discord_resources
            )
            VALUES (%s, %s, %s, %s, '{}'::jsonb, 'active', '{}'::jsonb)
            """,
            (
                chapter_id,
                f"Chapter {chapter_id}",
                template_id,
                Jsonb({"role_structure": [{"name": "member"}, {"name": "officer"}]}),
            ),
        )


def seed_role_holder(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    member_id: str,
    status: str = "active",
    triggers_succession: bool = True,
) -> UUID:
    ensure_chapter(db, chapter_id=chapter_id)
    role_id = uuid4()
    roster_entry_id = uuid4()
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO chapter_roles (
                id, chapter_id, template_id, name, ordinal, triggers_succession
            )
            VALUES (%s, %s, NULL, %s, 10, %s)
            """,
            (role_id, chapter_id, f"Role-{role_id.hex[:6]}", triggers_succession),
        )
        connection.execute(
            """
            INSERT INTO roster_entries (
                id, chapter_id, member_id, role_id, status, removal_metadata
            )
            VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
            """,
            (roster_entry_id, chapter_id, member_id, role_id, status),
        )
    insert_aggregate_head(
        db,
        aggregate_type="roster_entry",
        aggregate_id=str(roster_entry_id),
        version=1,
    )
    return role_id


def seed_application(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    applicant_id: UUID,
    owner_id: UUID | None,
    state: str,
) -> UUID:
    ensure_chapter(db, chapter_id=chapter_id)
    application_id = uuid4()
    now = datetime.now(UTC)
    with db.connection() as connection:
        existing_form = connection.execute(
            """
            SELECT id, version
            FROM form_definitions
            WHERE scope_kind = 'chapter' AND scope_id = %s
              AND status = 'current'
            ORDER BY version DESC
            LIMIT 1
            """,
            (chapter_id,),
        ).fetchone()
        if existing_form is None:
            form_id = uuid4()
            form_version = 1
            connection.execute(
                """
                INSERT INTO form_definitions (
                    id, scope_kind, scope_id, version, name, target_type, fields,
                    routing_rules, status, published_by_kind, published_by_id
                )
                VALUES (%s, 'chapter', %s, %s, 'Chapter Intake', 'chapter_membership',
                        '[]'::jsonb, %s, 'current', 'user', 'operator')
                """,
                (
                    form_id,
                    chapter_id,
                    form_version,
                    Jsonb({"schema_version": 1, "queue": "chapter_officers"}),
                ),
            )
        else:
            form_id = existing_form[0]
            form_version = int(existing_form[1])
    form_snapshot = {
        "schema_version": 1,
        "form_definition_id": str(form_id),
        "name": "Chapter Intake",
        "target_type": "chapter_membership",
        "scope_kind": "chapter",
        "scope_id": chapter_id,
        "form_version": form_version,
        "target_scope": {"scope_kind": "chapter", "scope_id": chapter_id},
        "fields": [],
        "routing_rules": {"schema_version": 1, "queue": "chapter_officers"},
    }
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO applications (
                id, applicant_id, form_definition_id, form_version, form_snapshot,
                target_scope_kind, target_scope_id, responses, state, owner_id,
                interview_thread_id, decision_reason, client_application_id,
                submitted_at, queued_at, claimed_at, review_started_at,
                decided_at, withdrawn_at
            )
            VALUES (%s, %s, %s, %s, %s, 'chapter', %s, '{}'::jsonb, %s, %s,
                    NULL, NULL, NULL, %s, %s, NULL, NULL, NULL, NULL)
            """,
            (
                application_id,
                applicant_id,
                form_id,
                form_version,
                Jsonb(form_snapshot),
                chapter_id,
                state,
                owner_id,
                now,
                now,
            ),
        )
    insert_aggregate_head(
        db,
        aggregate_type="application",
        aggregate_id=str(application_id),
        version=1,
    )
    return application_id


def seed_ticket(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    owner_id: str | None,
    state: str = "open",
    terminal_at: datetime | None = None,
) -> UUID:
    ensure_chapter(db, chapter_id=chapter_id)
    category_id = uuid4()
    ticket_id = uuid4()
    snapshot = {
        "schema_version": 1,
        "category_id": str(category_id),
        "name": f"Category-{category_id.hex[:6]}",
        "category_version": 1,
        "routing_scope": {
            "scope_kind": "chapter",
            "scope_id": chapter_id,
            "queue": "chapter_officers",
        },
        "privacy_level": "staff_only",
        "state_machine": {
            "schema_version": 1,
            "initial_state": "open",
            "states": [
                {"key": "open", "label": "Open", "terminal": False},
                {"key": "closed", "label": "Closed", "terminal": True},
            ],
            "edges": [],
        },
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
                snapshot["name"],
                Jsonb(snapshot["routing_scope"]),
                Jsonb(snapshot["state_machine"]),
            ),
        )
        connection.execute(
            """
            INSERT INTO tickets (
                id, category_id, category_version, category_snapshot, reporter_id,
                subject_id, state, priority, owner_id, resolution, client_ticket_id,
                terminal_at
            )
            VALUES (%s, %s, 1, %s, 'reporter', NULL, %s, 'normal', %s, NULL, NULL, %s)
            """,
            (ticket_id, category_id, Jsonb(snapshot), state, owner_id, terminal_at),
        )
    insert_aggregate_head(
        db,
        aggregate_type="ticket",
        aggregate_id=str(ticket_id),
        version=1,
    )
    return ticket_id
