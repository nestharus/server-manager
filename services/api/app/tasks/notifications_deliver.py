from __future__ import annotations

from typing import Callable
from uuid import UUID

from app.contracts.notifications import NotificationDeliveryResult
from app.contracts.scheduler import DeferredEffectRead
from app.repositories.db import PostgresDatabase
from app.repositories.notifications import NotificationsRepository
from app.services.notifications_delivery import (
    NotificationDeliveryPort,
    NotificationsDeliveryService,
)
from app.services.scheduler import register_scheduler_handler

globals()["_DELIVERY_PORT_FACTORY"] = None


class _UnconfiguredNotificationDeliveryPort:
    def deliver(self, _command) -> NotificationDeliveryResult:
        raise RuntimeError("notifications delivery port is not configured")


def _delivery_port() -> NotificationDeliveryPort:
    factory: Callable[[], NotificationDeliveryPort] | None = globals()[
        "_DELIVERY_PORT_FACTORY"
    ]
    if factory is None:
        return _UnconfiguredNotificationDeliveryPort()
    return factory()


@register_scheduler_handler("notifications_deliver")
def deliver_notification(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> NotificationDeliveryResult:
    envelope_id = UUID(str(effect.payload_json["envelope_id"]))
    return NotificationsDeliveryService(
        notifications_repo=NotificationsRepository(db),
        delivery_port=_delivery_port(),
    ).deliver_envelope(envelope_id)
