from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection

from app.contracts.mutations import (
    MutationRequest,
    MutationResult,
    StaleMutationError,
    StateChangeDraft,
)
from app.repositories.db import PostgresDatabase
from app.repositories.mutations import (
    advance_head,
    get_head_for_update,
    insert_action,
    insert_state_change,
)

REQUEST_SURFACE = "service:mutate_entity"
ERROR_MESSAGE_LIMIT = 500


def _format_etag(version: int) -> str:
    return f'"{version}"'


def _redact_payload(
    action_payload: dict[str, object],
    payload_allowlist: set[str] | None,
) -> dict[str, object]:
    if not payload_allowlist:
        return {}

    return {
        key: value
        for key, value in action_payload.items()
        if key in payload_allowlist
    }


def _failure_metadata(error: Exception) -> dict[str, object]:
    return {
        "error_type": error.__class__.__name__,
        "message": str(error)[:ERROR_MESSAGE_LIMIT],
    }


def mutate_entity(
    *,
    db: PostgresDatabase,
    aggregate_type: str,
    aggregate_id: int,
    request: MutationRequest,
    action_type: str,
    action_payload: dict[str, object],
    payload_allowlist: set[str] | None,
    mutate_projection: Callable[[Connection[Any]], StateChangeDraft],
) -> MutationResult:
    redacted_payload = _redact_payload(action_payload, payload_allowlist)
    stale_error: StaleMutationError | None = None

    try:
        with db.transaction() as connection:
            head = get_head_for_update(
                connection,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            )
            if head is None:
                raise RuntimeError(
                    f"missing aggregate head for {aggregate_type}#{aggregate_id}",
                )

            if head.current_seq != request.expected_version:
                insert_action(
                    connection,
                    action_type=action_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_kind=request.actor_kind,
                    actor_id=request.actor_id,
                    request_surface=REQUEST_SURFACE,
                    request_json=redacted_payload,
                    status="rejected",
                    reason_text=(
                        f"expected_version={request.expected_version} "
                        f"current_version={head.current_seq}"
                    ),
                )
                stale_error = StaleMutationError(
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    expected_version=request.expected_version,
                    current_version=head.current_seq,
                )
            else:
                action_id = insert_action(
                    connection,
                    action_type=action_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_kind=request.actor_kind,
                    actor_id=request.actor_id,
                    request_surface=REQUEST_SURFACE,
                    request_json=redacted_payload,
                    status="accepted",
                    reason_text=request.reason_text,
                )
                state_change = mutate_projection(connection)
                new_version = head.current_seq + 1
                change_id = insert_state_change(
                    connection,
                    action_id=action_id,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    aggregate_seq=new_version,
                    change_type=state_change.change_type,
                    payload_json=state_change.payload_json,
                    diff_json=state_change.diff_json,
                )
                advance_head(
                    connection,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    new_version=new_version,
                    latest_change_id=change_id,
                )

        if stale_error is not None:
            raise stale_error

        return MutationResult(version=new_version, etag=_format_etag(new_version))
    except StaleMutationError:
        raise
    except Exception as error:
        with db.transaction() as failure_connection:
            insert_action(
                failure_connection,
                action_type=action_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                actor_kind=request.actor_kind,
                actor_id=request.actor_id,
                request_surface=REQUEST_SURFACE,
                request_json=redacted_payload,
                status="failed",
                reason_text=request.reason_text,
                error_metadata=_failure_metadata(error),
            )
        raise
