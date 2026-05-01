from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


FILE_FIELD_ID = "character_sheet"
FILE_ACCEPT = ["image/png", "application/pdf"]
FILE_MAX_SIZE_BYTES = 1_048_576


def file_field(
    *,
    field_id: str = FILE_FIELD_ID,
    required: bool = True,
    page: int = 1,
    visible_when: dict[str, Any] | None = None,
    accept: list[str] | None = None,
    max_size_bytes: int = FILE_MAX_SIZE_BYTES,
) -> dict[str, Any]:
    field: dict[str, Any] = {
        "id": field_id,
        "type": "file",
        "label": "Character sheet",
        "required": required,
        "accept": accept or list(FILE_ACCEPT),
        "max_size_bytes": max_size_bytes,
        "page": page,
    }
    if visible_when is not None:
        field["visible_when"] = visible_when
    return field


def text_field(
    *,
    field_id: str = "character_name",
    label: str = "Character name",
    required: bool = True,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "id": field_id,
        "type": "short",
        "label": label,
        "required": required,
        "max_length": 64,
        "page": page,
    }


def long_text_field(
    *,
    field_id: str = "application_text",
    label: str = "Application text",
    required: bool = True,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "id": field_id,
        "type": "long",
        "label": label,
        "required": required,
        "max_length": 4000,
        "page": page,
    }


def boolean_field(
    *,
    field_id: str = "has_sheet",
    label: str = "Has a character sheet",
    required: bool = True,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "id": field_id,
        "type": "boolean",
        "label": label,
        "required": required,
        "page": page,
    }


def file_object_key(
    *,
    application_id: UUID | None = None,
    field_id: str = FILE_FIELD_ID,
    object_id: UUID | None = None,
) -> str:
    return f"applications/{application_id or uuid4()}/{field_id}/{object_id or uuid4()}"


def file_response(
    *,
    object_key: str | None = None,
    content_type: str = "image/png",
    size_bytes: int = 1024,
    field_id: str = FILE_FIELD_ID,
    application_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "object_key": object_key
        or file_object_key(application_id=application_id, field_id=field_id),
        "content_type": content_type,
        "size_bytes": size_bytes,
    }


def seed_global_file_field_form(
    db: PostgresDatabase,
    *,
    fields: list[dict[str, Any]] | None = None,
    form_id: UUID | None = None,
    name: str = "Public file upload application",
    routing_rules: dict[str, Any] | None = None,
) -> UUID:
    resolved_form_id = form_id or uuid4()
    resolved_fields = fields or [
        text_field(),
        long_text_field(),
        file_field(),
    ]
    resolved_routing_rules = routing_rules or {
        "schema_version": 1,
        "queue": "chapter_officers",
        "review_scope": {"scope_kind": "global", "scope_id": None},
    }
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
                %s,
                'chapter_membership',
                %s,
                %s,
                'current',
                'service',
                'init-137-test'
            )
            """,
            (resolved_form_id, name, Jsonb(resolved_fields), Jsonb(resolved_routing_rules)),
        )
    return resolved_form_id


def seed_global_chapter_selector_file_form(db: PostgresDatabase) -> UUID:
    return seed_global_file_field_form(
        db,
        fields=[
            {
                "id": "chapter",
                "type": "chapter_select",
                "label": "Chapter",
                "required": True,
                "placeholder": "Choose a chapter",
                "page": 1,
            },
            text_field(page=1),
            long_text_field(page=1),
            file_field(required=False, page=1),
        ],
        name="Public chapter selector file application",
        routing_rules={"schema_version": 1, "queue": "chapter_officers"},
    )


def fetch_application_response_row(
    db: PostgresDatabase,
    application_id: UUID,
) -> dict[str, Any]:
    with db.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT id, responses, form_snapshot, target_scope_kind, target_scope_id
            FROM applications
            WHERE id = %s
            """,
            (application_id,),
        ).fetchone()
    assert row is not None, f"missing application row {application_id}"
    return dict(row)
