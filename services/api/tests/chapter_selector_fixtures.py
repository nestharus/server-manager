from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


CHAPTER_SELECTOR_FIELD_ID = "chapter"
_DEFAULT_SCOPE_ID = object()


def seed_chapter(
    db: PostgresDatabase,
    *,
    chapter_id: str | None = None,
    name: str,
    state: str = "active",
) -> str:
    resolved_chapter_id = chapter_id or f"chapter-{uuid4().hex[:12]}"
    template_id = uuid4()
    with db.connection() as connection:
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
            VALUES (%s, %s, 1, %s, 1, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
            """,
            (template_id, template_id, f"Template for {name}"),
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
            VALUES (%s, %s, %s, %s, '{}'::jsonb, %s, '{}'::jsonb)
            """,
            (
                resolved_chapter_id,
                name,
                template_id,
                Jsonb({"template_id": str(template_id), "schema_version": 1}),
                state,
            ),
        )
        connection.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type,
                aggregate_id,
                current_seq,
                latest_change_id
            )
            VALUES ('chapter', %s, 1, NULL)
            """,
            (resolved_chapter_id,),
        )
    return resolved_chapter_id


def chapter_selector_fields() -> list[dict[str, Any]]:
    return [
        {
            "id": CHAPTER_SELECTOR_FIELD_ID,
            "type": "chapter_select",
            "label": "Chapter",
            "required": True,
            "placeholder": "Choose a chapter",
        },
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


def seed_global_chapter_selector_form(db: PostgresDatabase) -> UUID:
    form_id = uuid4()
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE form_definitions
            SET status = 'archived',
                archived_at = CURRENT_TIMESTAMP
            WHERE scope_kind = 'global'
              AND scope_id IS NULL
              AND status = 'current'
            """
        )
        connection.execute(
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
                published_by_id
            )
            VALUES (
                %s,
                'global',
                NULL,
                1,
                'Public Application',
                'chapter_membership',
                %s,
                %s,
                'current',
                'service',
                'init-135-test'
            )
            """,
            (
                form_id,
                Jsonb(chapter_selector_fields()),
                Jsonb({"schema_version": 1, "queue": "chapter_officers"}),
            ),
        )
    return form_id


def chapter_selector_public_payload(
    *,
    chapter_id: str,
    client_application_id: str | None = None,
    responses: dict[str, Any] | None = None,
    scope_kind: str = "chapter",
    scope_id: str | None | object = _DEFAULT_SCOPE_ID,
) -> dict[str, Any]:
    resolved_scope_id = chapter_id if scope_id is _DEFAULT_SCOPE_ID else scope_id
    payload: dict[str, Any] = {
        "scope": {"scope_kind": scope_kind, "scope_id": resolved_scope_id},
        "responses": responses
        if responses is not None
        else {
            CHAPTER_SELECTOR_FIELD_ID: chapter_id,
            "character_name": "Test Applicant",
            "application_text": "I want to join scheduled guild activities.",
        },
    }
    if client_application_id is not None:
        payload["client_application_id"] = client_application_id
    return payload


def fetch_application_target_row(
    database_url: str,
    application_id: UUID,
) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                target_scope_kind,
                target_scope_id,
                form_snapshot,
                responses,
                state,
                client_application_id
            FROM applications
            WHERE id = %s
            """,
            (application_id,),
        ).fetchone()
    assert row is not None, f"missing application row {application_id}"
    return dict(row)


def seed_form_definition(
    db: PostgresDatabase,
    *,
    form_id: UUID,
    version: int,
    status: str = "current",
    fields: list[dict[str, Any]] | None = None,
    published_by_kind: str = "service",
    published_by_id: str = "init-135-test",
    archived_at: datetime | None = None,
) -> None:
    with db.connection() as connection:
        connection.execute(
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
                archived_at
            )
            VALUES (
                %s,
                'global',
                NULL,
                %s,
                'Public application intake (global)',
                'chapter_membership',
                %s,
                '{}'::jsonb,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                form_id,
                version,
                Jsonb(fields or chapter_selector_fields()),
                status,
                published_by_kind,
                published_by_id,
                archived_at,
            ),
        )


def fetch_global_forms(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, version, status, archived_at, fields, routing_rules
                FROM form_definitions
                WHERE scope_kind = 'global' AND scope_id IS NULL
                ORDER BY version ASC, created_at ASC, id ASC
                """
            ).fetchall()
        ]


def fetch_form_aggregate_head(database_url: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT aggregate_type, aggregate_id, current_seq, latest_change_id
            FROM aggregate_heads
            WHERE aggregate_type = 'application_form'
              AND aggregate_id = 'application_form|global|'
            """
        ).fetchone()
    return None if row is None else dict(row)


def fetch_form_actions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT action_type, aggregate_type, aggregate_id, request_json
                FROM activity_actions
                WHERE aggregate_type = 'application_form'
                  AND aggregate_id = 'application_form|global|'
                ORDER BY id ASC
                """
            ).fetchall()
        ]


def fetch_form_state_changes(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT change_type, aggregate_seq, payload_json
                FROM activity_state_changes
                WHERE aggregate_type = 'application_form'
                  AND aggregate_id = 'application_form|global|'
                ORDER BY id ASC
                """
            ).fetchall()
        ]
