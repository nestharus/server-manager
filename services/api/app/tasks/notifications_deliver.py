from __future__ import annotations

from typing import Callable
from uuid import UUID

from app.contracts.notifications import NotificationDeliveryResult
from app.contracts.scheduler import DeferredEffectRead
from app.repositories.db import PostgresDatabase
from app.services.notifications_delivery import NotificationDeliveryPort, deliver_envelope
from app.services.scheduler import register_scheduler_handler

_DB: PostgresDatabase | None = None
_DELIVERY_PORT_FACTORY: Callable[[], NotificationDeliveryPort] | None = None
delivery_port: NotificationDeliveryPort | None = None


def configure_notifications_deliver(
    *,
    db: PostgresDatabase,
    delivery_port_factory: Callable[[], NotificationDeliveryPort] | None = None,
) -> None:
    global _DB, _DELIVERY_PORT_FACTORY
    _DB = db
    _DELIVERY_PORT_FACTORY = delivery_port_factory


def get_delivery_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def get_delivery_port() -> NotificationDeliveryPort:
    if delivery_port is not None:
        return delivery_port
    if _DELIVERY_PORT_FACTORY is None:
        raise RuntimeError("notifications delivery port is not configured")
    return _DELIVERY_PORT_FACTORY()


@register_scheduler_handler("notifications_deliver")
def deliver_notification(effect: DeferredEffectRead) -> NotificationDeliveryResult:
    envelope_id = UUID(str(effect.payload_json["envelope_id"]))
    return deliver_envelope(
        get_delivery_db(),
        envelope_id,
        delivery_port=get_delivery_port(),
    )
