from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from pydantic import TypeAdapter

from app.contracts.base import validated_update
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.roster import (
    InvalidRosterStatusTransitionError,
    RosterEntryCreate,
    RosterEntryRead,
    RosterRoleNotFoundError,
    RosterStatus,
)
from app.repositories.db import PostgresDatabase
from app.repositories.roster import (
    fetch_roster_entry,
    insert_roster_entry,
    update_roster_status,
)
from app.services.mutations import mutate_entity


_roster_status_adapter = TypeAdapter(RosterStatus)


def _make_request(expected_version: int, request_surface: str) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="system",
        actor_id="roster-service",
        reason_text=None,
        request_surface=request_surface,
    )


def _validate_roster_transition(current_status: str, new_status: str) -> None:
    allowed = {
        "active": {"on_leave", "under_review", "removed"},
        "on_leave": {"active", "removed"},
        "under_review": {"active", "removed"},
        "removed": set(),
    }
    if new_status not in allowed[current_status]:
        raise InvalidRosterStatusTransitionError(current_status, new_status)


def _fetch_current_version(
    connection: Connection[Any],
    *,
    aggregate_type: str,
    aggregate_id: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT current_seq
        FROM aggregate_heads
        WHERE aggregate_type = %s AND aggregate_id = %s
        """,
        (aggregate_type, aggregate_id),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def create_roster_entry(
    db: PostgresDatabase,
    request: RosterEntryCreate,
) -> MutationResult:
    entry_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_roster_entry(
            connection,
            row={"id": entry_id, **request.model_dump(mode="python")},
        )
        payload = RosterEntryRead(
            id=entry_id,
            created_at=requested_at(),
            **request.model_dump(mode="python"),
        ).model_dump(mode="json")
        return StateChangeDraft(
            change_type="roster_entry.created",
            payload_json=payload,
        )

    try:
        return mutate_entity(
            db=db,
            aggregate_type="roster_entry",
            aggregate_id=str(entry_id),
            request=_make_request(0, "service:roster.create_roster_entry"),
            action_type="roster_entry.create",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump().keys()),
            mutate_projection=mutate_projection,
            scope_kind="chapter",
            scope_id=request.chapter_id,
        )
    except psycopg.errors.ForeignKeyViolation as exc:
        raise RosterRoleNotFoundError(request.role_id) from exc


def requested_at() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


def read_roster_entry(
    db: PostgresDatabase,
    entry_id: UUID,
) -> RosterEntryRead:
    with db.connection() as connection:
        row = fetch_roster_entry(connection, entry_id)
    if row is None:
        raise LookupError(f"roster entry {entry_id} was not found")
    return RosterEntryRead.model_validate(row)


def transition_roster_status(
    db: PostgresDatabase,
    *,
    entry_id: UUID,
    new_status: str,
    expected_version: int | None = None,
) -> MutationResult:
    validated_status = _roster_status_adapter.validate_python(new_status)
    current = read_roster_entry(db, entry_id)
    _validate_roster_transition(current.status, validated_status)
    updated = validated_update(current, {"status": validated_status})

    if expected_version is None:
        with db.connection() as connection:
            current_version = _fetch_current_version(
                connection,
                aggregate_type="roster_entry",
                aggregate_id=str(entry_id),
            )
        if current_version is None:
            raise LookupError(f"missing aggregate roster_entry#{entry_id}")
        expected_version = current_version

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        updated_count = update_roster_status(
            connection,
            entry_id=entry_id,
            status=updated.status,
        )
        if updated_count != 1:
            raise LookupError(f"roster entry {entry_id} was not found")
        return StateChangeDraft(
            change_type="roster_entry.status_updated",
            payload_json=updated.model_dump(mode="json"),
        )

    return mutate_entity(
        db=db,
        aggregate_type="roster_entry",
        aggregate_id=str(entry_id),
        request=_make_request(
            expected_version,
            "service:roster.transition_roster_status",
        ),
        action_type="roster_entry.update_status",
        action_payload={"status": updated.status},
        payload_allowlist={"status"},
        mutate_projection=mutate_projection,
        scope_kind="chapter",
        scope_id=current.chapter_id,
    )
