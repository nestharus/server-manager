from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import (
    MissingAggregateError,
    MutationRequest,
    MutationResult,
    StaleMutationError,
    StateChangeDraft,
)
from app.contracts.scope import ScopeKind
from app.core.context import (
    MissingCorrelationContextError,
    get_current_audit_context,
    use_audit_context,
)
from app.repositories.db import PostgresDatabase
from app.repositories.mutations import (
    advance_head,
    get_head_for_update,
    insert_action,
    insert_state_change,
)

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
    aggregate_id: str,
    request: MutationRequest,
    action_type: str,
    action_payload: dict[str, object],
    payload_allowlist: set[str] | None,
    mutate_projection: Callable[[Connection[Any]], StateChangeDraft],
    scope_kind: ScopeKind | None = None,
    scope_id: str | None = None,
    connection: Connection[Any] | None = None,
) -> MutationResult:
    redacted_payload = _redact_payload(action_payload, payload_allowlist)
    stale_error: StaleMutationError | None = None
    current_ctx = get_current_audit_context()
    resolved_correlation_id = request.correlation_id
    if resolved_correlation_id is None:
        if current_ctx is None:
            raise MissingCorrelationContextError()
        resolved_correlation_id = current_ctx.correlation_id

    resolved_causation_id = request.causation_id
    if resolved_causation_id is None and current_ctx is not None:
        resolved_causation_id = current_ctx.causation_id

    resolved_ctx = AuditContextRead(
        correlation_id=resolved_correlation_id,
        causation_id=resolved_causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=resolved_correlation_id,
            x_causation_id=resolved_causation_id,
        ),
    )

    def _run_mutation(active_connection: Connection[Any]) -> MutationResult | None:
        nonlocal stale_error
        with use_audit_context(resolved_ctx):
            if request.expected_version == 0:
                active_connection.execute(
                    """
                    INSERT INTO aggregate_heads (
                        aggregate_type,
                        aggregate_id,
                        current_seq,
                        latest_change_id
                    )
                    VALUES (%s, %s, 0, NULL)
                    ON CONFLICT DO NOTHING
                    """,
                    (aggregate_type, aggregate_id),
                )

            head = get_head_for_update(
                active_connection,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            )
            if head is None:
                raise MissingAggregateError(
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                )

            if head.current_seq != request.expected_version:
                insert_action(
                    active_connection,
                    action_type=action_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_kind=request.actor_kind,
                    actor_id=request.actor_id,
                    correlation_id=resolved_ctx.correlation_id,
                    causation_id=resolved_ctx.causation_id,
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    request_surface=request.request_surface,
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
                    active_connection,
                    action_type=action_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_kind=request.actor_kind,
                    actor_id=request.actor_id,
                    correlation_id=resolved_ctx.correlation_id,
                    causation_id=resolved_ctx.causation_id,
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    request_surface=request.request_surface,
                    request_json=redacted_payload,
                    status="accepted",
                    reason_text=request.reason_text,
                )
                state_change = mutate_projection(active_connection)
                new_version = head.current_seq + 1
                change_id = insert_state_change(
                    active_connection,
                    action_id=action_id,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    aggregate_seq=new_version,
                    change_type=state_change.change_type,
                    payload_json=state_change.payload_json,
                    diff_json=state_change.diff_json,
                )
                advance_head(
                    active_connection,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    new_version=new_version,
                    latest_change_id=change_id,
                )
                return MutationResult(version=new_version, etag=_format_etag(new_version))

        if stale_error is not None:
            return None
        raise RuntimeError("mutation finished without result")

    try:
        if connection is None:
            with db.transaction() as transaction_connection:
                result = _run_mutation(transaction_connection)
        else:
            result = _run_mutation(connection)

        if stale_error is not None:
            raise stale_error
        if result is None:
            raise RuntimeError("mutation finished without result")
        return result
    except StaleMutationError:
        raise
    except Exception as error:
        with use_audit_context(resolved_ctx):
            with db.transaction() as failure_connection:
                insert_action(
                    failure_connection,
                    action_type=action_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_kind=request.actor_kind,
                    actor_id=request.actor_id,
                    correlation_id=resolved_ctx.correlation_id,
                    causation_id=resolved_ctx.causation_id,
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    request_surface=request.request_surface,
                    request_json=redacted_payload,
                    status="failed",
                    reason_text=request.reason_text,
                    error_metadata=_failure_metadata(error),
                )
        raise
