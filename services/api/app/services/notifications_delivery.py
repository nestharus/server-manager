from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.contracts.notifications import (
    NotificationDeliveryCommand,
    NotificationDeliveryError,
    NotificationDeliveryResult,
    NotificationEnvelopeRead,
)
from app.repositories.notifications import NotificationsRepository
from app.services.scheduler import LEASE_SECONDS


class NotificationDeliveryPort(Protocol):
    def deliver(
        self, command: NotificationDeliveryCommand
    ) -> NotificationDeliveryResult: ...


def _envelope_from_row(row: dict[str, Any]) -> NotificationEnvelopeRead:
    return NotificationEnvelopeRead.model_validate(row)


def _error_payload(error: Exception) -> dict[str, Any]:
    definitive_failure = (
        error.definitive_failure
        if isinstance(error, NotificationDeliveryError)
        else False
    )
    return {
        "error_type": error.__class__.__name__,
        "message": str(error),
        "definitive_failure": definitive_failure,
    }


class NotificationsDeliveryService:
    def __init__(
        self,
        notifications_repo: NotificationsRepository,
        delivery_port: NotificationDeliveryPort,
    ) -> None:
        self._notifications_repo = notifications_repo
        self._delivery_port = delivery_port

    def deliver_envelope(
        self,
        envelope_id: UUID,
        *,
        worker_id: str = "notification-dispatcher",
    ) -> NotificationDeliveryResult:
        db = self._notifications_repo.db
        now = datetime.now(UTC)
        with db.transaction() as connection:
            claimed_row = self._notifications_repo._claim_notification_envelope_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                now=now,
                lease_seconds=LEASE_SECONDS,
            )

        if claimed_row is None:
            with db.connection() as connection:
                existing = self._notifications_repo._fetch_notification_envelope_on(
                    connection,
                    envelope_id,
                )
            if existing is None:
                raise LookupError(f"notification envelope {envelope_id} was not found")
            envelope = _envelope_from_row(existing)
            if envelope.delivery_status in {"delivered", "delivered_in_flight"}:
                return NotificationDeliveryResult(
                    envelope_id=envelope.id,
                    delivery_status=envelope.delivery_status,
                    discord_message_id=envelope.discord_message_id,
                    delivered_at=envelope.delivered_at,
                    noop=True,
                )
            return NotificationDeliveryResult(
                envelope_id=envelope.id,
                delivery_status=envelope.delivery_status,
                noop=True,
            )

        with db.transaction() as connection:
            in_flight_row = (
                self._notifications_repo._mark_envelope_delivered_in_flight_on(
                    connection,
                    envelope_id=envelope_id,
                    worker_id=worker_id,
                    now=datetime.now(UTC),
                )
            )
            if in_flight_row is None:
                current = self._notifications_repo._fetch_notification_envelope_on(
                    connection,
                    envelope_id,
                )
                if current is None:
                    raise LookupError(
                        f"notification envelope {envelope_id} was not found"
                    )
                current_envelope = _envelope_from_row(current)
                return NotificationDeliveryResult(
                    envelope_id=current_envelope.id,
                    delivery_status=current_envelope.delivery_status,
                    discord_message_id=current_envelope.discord_message_id,
                    delivered_at=current_envelope.delivered_at,
                    noop=True,
                )
            command = NotificationDeliveryCommand(
                envelope=_envelope_from_row(in_flight_row)
            )

        try:
            result = self._delivery_port.deliver(command)
        except Exception as error:
            definitive_failure = (
                error.definitive_failure
                if isinstance(error, NotificationDeliveryError)
                else False
            )
            with db.transaction() as connection:
                if definitive_failure:
                    row = self._notifications_repo._mark_envelope_delivery_failure_on(
                        connection,
                        envelope_id=envelope_id,
                        worker_id=worker_id,
                        now=datetime.now(UTC),
                        error_payload=_error_payload(error),
                    )
                    if row is None:
                        raise RuntimeError(
                            "failed to record notification delivery failure"
                        )
                    envelope = _envelope_from_row(row)
                    return NotificationDeliveryResult(
                        envelope_id=envelope.id,
                        delivery_status=envelope.delivery_status,
                        noop=False,
                    )
                updated = self._notifications_repo._mark_envelope_ambiguous_failure_on(
                    connection,
                    envelope_id=envelope_id,
                    worker_id=worker_id,
                    now=datetime.now(UTC),
                    error_payload=_error_payload(error),
                )
                if updated != 1:
                    raise RuntimeError(
                        "failed to record ambiguous notification delivery failure"
                    )
            raise

        with db.transaction() as connection:
            updated = self._notifications_repo._mark_envelope_delivered_on(
                connection,
                envelope_id=envelope_id,
                worker_id=worker_id,
                discord_message_id=result.discord_message_id,
                delivered_at=result.delivered_at or datetime.now(UTC),
            )
            if updated != 1:
                raise RuntimeError("failed to mark notification envelope delivered")
        return NotificationDeliveryResult(
            envelope_id=envelope_id,
            delivery_status="delivered",
            discord_message_id=result.discord_message_id,
            delivered_at=result.delivered_at,
            noop=False,
        )


__all__ = ["NotificationDeliveryPort", "NotificationsDeliveryService"]
