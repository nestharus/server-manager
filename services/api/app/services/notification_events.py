from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.notifications import NotificationEventDraft, NotificationEventRead
from app.contracts.scheduler import DeferredEffectCreate
from app.core.context import MissingCorrelationContextError, get_current_audit_context
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.notification_events import NotificationEventsRepository
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


def _redact_payload(
    payload_json: dict[str, Any],
    payload_allowlist: frozenset[str] | None,
) -> dict[str, Any]:
    if payload_allowlist is None:
        return {}
    return {
        key: value for key, value in payload_json.items() if key in payload_allowlist
    }


class NotificationEventsService:
    def __init__(
        self,
        notification_events_repo: NotificationEventsRepository,
        deferred_effects_repo: DeferredEffectsRepository,
        mutations_callable,
    ) -> None:
        self._notification_events_repo = notification_events_repo
        self._deferred_effects_repo = deferred_effects_repo
        self._mutations_callable = mutations_callable

    def emit(
        self,
        connection: Connection[Any] | None = None,
        *,
        event: NotificationEventDraft,
        actor: ActorIdentity,  # noqa: ARG002 - reserved for worker-attribution parity
        payload_allowlist: frozenset[str] | None = None,
    ) -> NotificationEventRead:
        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        redacted_payload = _redact_payload(event.payload_json, payload_allowlist)

        def _emit(active_connection: Connection[Any]) -> NotificationEventRead:
            event_id, created_at = (
                self._notification_events_repo._insert_notification_event_on(
                    active_connection,
                    correlation_id=ctx.correlation_id,
                    causation_id=ctx.causation_id,
                    draft=event,
                    payload_json=redacted_payload,
                )
            )
            self._deferred_effects_repo._enqueue_effect_on(
                active_connection,
                effect=DeferredEffectCreate(
                    subsystem="notifications",
                    effect_type="notifications_materialize",
                    idempotency_key=f"notifications:materialize:{event_id}",
                    payload_json={"event_id": str(event_id)},
                    consequence_level="safe",
                    correlation_id=ctx.correlation_id,
                    causation_id=ctx.causation_id,
                ),
                correlation_id=ctx.correlation_id,
                max_attempts=DEFAULT_MAX_ATTEMPTS,
            )
            return NotificationEventRead(
                id=event_id,
                event_type=event.event_type,
                correlation_id=ctx.correlation_id,
                causation_id=ctx.causation_id,
                scope_kind=event.scope_kind,
                scope_id=event.scope_id,
                payload=redacted_payload,
                created_at=created_at,
            )

        if connection is not None:
            return _emit(connection)
        with self._notification_events_repo.db.transaction() as active_connection:
            return _emit(active_connection)

    def replay(self, correlation_id: UUID) -> list[NotificationEventRead]:
        with self._notification_events_repo.db.connection() as connection:
            rows = self._notification_events_repo._list_for_correlation_on(
                connection,
                correlation_id,
            )
        return [
            NotificationEventRead(
                id=row["id"],
                event_type=row["event_type"],
                correlation_id=row["correlation_id"],
                causation_id=row["causation_id"],
                scope_kind=row["scope_kind"],
                scope_id=row["scope_id"],
                payload=row["payload_json"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


__all__ = ["NotificationEventsService"]
