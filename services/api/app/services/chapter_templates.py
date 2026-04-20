from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChapterTemplateCreate,
    ChapterTemplateRead,
    TemplateSchemaVersionMismatchError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.chapter_templates import (
    fetch_chapter_template,
    insert_chapter_template,
)
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity


def _make_request(expected_version: int, request_surface: str) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="system",
        actor_id="chapter-templates-service",
        reason_text=None,
        request_surface=request_surface,
    )


def _validate_schema_version(schema_version: int) -> None:
    if schema_version != CURRENT_TEMPLATE_SCHEMA_VERSION:
        raise TemplateSchemaVersionMismatchError(schema_version)


def create_chapter_template(
    db: PostgresDatabase,
    request: ChapterTemplateCreate,
) -> MutationResult:
    template_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_chapter_template(
            connection,
            row={
                "id": template_id,
                **request.model_dump(mode="python"),
            },
        )
        payload = ChapterTemplateRead(
            id=template_id,
            created_at=requested_at(),
            **request.model_dump(mode="python"),
        ).model_dump(mode="json")
        return StateChangeDraft(
            change_type="chapter_template.created",
            payload_json=payload,
        )

    return mutate_entity(
        db=db,
        aggregate_type="chapter_template",
        aggregate_id=str(template_id),
        request=_make_request(
            0,
            "service:chapter_templates.create_chapter_template",
        ),
        action_type="chapter_template.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump().keys()),
        mutate_projection=mutate_projection,
    )


def requested_at() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


def read_chapter_template(
    db: PostgresDatabase,
    template_id: UUID,
) -> ChapterTemplateRead:
    with db.connection() as connection:
        row = fetch_chapter_template(connection, template_id)
    if row is None:
        raise LookupError(f"chapter template {template_id} was not found")
    _validate_schema_version(int(row["schema_version"]))
    return ChapterTemplateRead.model_validate(row)

