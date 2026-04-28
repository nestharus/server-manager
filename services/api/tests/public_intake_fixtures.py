from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


PUBLIC_SUBMIT_SURFACE = "api:/api/v1/public/applications"
AUTHENTICATED_SUBMIT_SURFACE = "api:/api/v1/applications"
PUBLIC_INTAKE_ACTOR_KIND = "service"
PUBLIC_INTAKE_ACTOR_ID = "public-intake"
PUBLIC_MEMBER_SALT = "local-public-intake-salt"


def public_application_payload(
    *,
    client_application_id: str | None = "browser-submission-1",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scope": {"scope_kind": "global", "scope_id": None},
        "responses": {
            "character_name": "Test Applicant",
            "application_text": "I want to join scheduled guild activities.",
        },
    }
    if client_application_id is not None:
        payload["client_application_id"] = client_application_id
    return payload


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


def seed_global_public_application_form(db: PostgresDatabase) -> UUID:
    form_id = uuid4()
    fields = [
        {
            "id": "character_name",
            "type": "short",
            "label": "Character name",
            "required": True,
            "max_length": 64,
        },
        {
            "id": "application_text",
            "type": "long",
            "label": "Application text",
            "required": True,
            "max_length": 4000,
        },
    ]
    routing_rules = {
        "schema_version": 1,
        "queue": "chapter_officers",
        "review_scope": {"scope_kind": "global", "scope_id": None},
    }
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE form_definitions
            SET status = 'archived'
            WHERE scope_kind = 'global'
              AND scope_id IS NULL
              AND status = 'current'
            """
        )
        connection.execute(
            """
            INSERT INTO form_definitions (
                id, scope_kind, scope_id, version, name, target_type, fields,
                routing_rules, status, published_by_kind, published_by_id
            )
            VALUES (
                %s, 'global', NULL, 1, 'Public Application', 'chapter_membership',
                %s, %s, 'current', 'service', 'public-intake'
            )
            """,
            (form_id, Jsonb(fields), Jsonb(routing_rules)),
        )
    return form_id


def create_real_member(db: PostgresDatabase, discord_user_id: str) -> UUID:
    member_id = uuid4()
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO members (id, discord_user_id, joined_at, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (member_id, discord_user_id, datetime.now(UTC)),
        )
        connection.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type, aggregate_id, current_seq, latest_change_id
            )
            VALUES ('member', %s, 1, NULL)
            """,
            (str(member_id),),
        )
    return member_id


def grant_application_submit(db: PostgresDatabase, actor_id: str) -> None:
    with use_audit_context(audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
            permissions=frozenset({"application.submit"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def authenticated_submission(applicant_id: UUID, *, client_id: str) -> dict[str, Any]:
    return {
        "applicant_id": applicant_id,
        **public_application_payload(client_application_id=client_id),
    }


def fetch_application_row(database_url: str, application_id: UUID) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT
                a.id,
                a.applicant_id,
                a.state,
                a.client_application_id,
                h.current_seq AS version,
                m.discord_user_id AS applicant_discord_user_id
            FROM applications AS a
            JOIN members AS m ON m.id = a.applicant_id
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'application'
             AND h.aggregate_id = a.id::text
            WHERE a.id = %s
            """,
            (application_id,),
        ).fetchone()
    assert row is not None, f"missing application row {application_id}"
    return dict(row)


def fetch_route_reviews(database_url: str, application_id: UUID) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT action, actor_kind, actor_id
                FROM application_reviews
                WHERE application_id = %s AND action = 'route'
                ORDER BY recorded_at ASC
                """,
                (application_id,),
            ).fetchall()
        ]


def fetch_application_actions(database_url: str, application_id: UUID) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    action_type,
                    actor_kind,
                    actor_id,
                    request_surface,
                    correlation_id,
                    request_json
                FROM activity_actions
                WHERE aggregate_type = 'application'
                  AND aggregate_id = %s
                ORDER BY recorded_at ASC
                """,
                (str(application_id),),
            ).fetchall()
        ]


def count_members_by_discord_id(database_url: str, discord_user_id: str) -> int:
    with psycopg.connect(database_url) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM members WHERE discord_user_id = %s",
                (discord_user_id,),
            ).fetchone()[0]
        )


def fetch_member_discord_ids(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT discord_user_id FROM members ORDER BY discord_user_id"
            ).fetchall()
        ]


def assert_risk_annotation(
    *,
    group: str,
    named_risk: str,
    level: str,
    source: str,
) -> None:
    assert group.startswith("TG-")
    assert named_risk
    assert level in {"unit", "component", "particular-integration", "end-to-end"}
    assert source
