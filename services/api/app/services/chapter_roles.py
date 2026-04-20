from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.chapter_roles import ChapterRoleCreate, ChapterRoleRead
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.chapter_roles import fetch_chapter_role, insert_chapter_role
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity


def _make_request(expected_version: int, request_surface: str) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="system",
        actor_id="chapter-roles-service",
        reason_text=None,
        request_surface=request_surface,
    )


def create_chapter_role(
    db: PostgresDatabase,
    request: ChapterRoleCreate,
) -> MutationResult:
    role_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_chapter_role(
            connection,
            row={"id": role_id, **request.model_dump(mode="python")},
        )
        payload = ChapterRoleRead(
            id=role_id,
            created_at=requested_at(),
            **request.model_dump(mode="python"),
        ).model_dump(mode="json")
        return StateChangeDraft(
            change_type="chapter_role.created",
            payload_json=payload,
        )

    return mutate_entity(
        db=db,
        aggregate_type="chapter_role",
        aggregate_id=str(role_id),
        request=_make_request(0, "service:chapter_roles.create_chapter_role"),
        action_type="chapter_role.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump().keys()),
        mutate_projection=mutate_projection,
    )


def requested_at() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


def read_chapter_role(
    db: PostgresDatabase,
    role_id: UUID,
) -> ChapterRoleRead:
    with db.connection() as connection:
        row = fetch_chapter_role(connection, role_id)
    if row is None:
        raise LookupError(f"chapter role {role_id} was not found")
    return ChapterRoleRead.model_validate(row)

