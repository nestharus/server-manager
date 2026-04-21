from __future__ import annotations

from uuid import UUID

from app.contracts.notifications import NotificationMaterializationResult
from app.contracts.scheduler import DeferredEffectRead
from app.repositories.db import PostgresDatabase
from app.services.notifications_materialize import materialize_event
from app.services.scheduler import register_scheduler_handler

_DB: PostgresDatabase | None = None


def configure_notifications_materialize(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_materialize_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


@register_scheduler_handler("notifications_materialize")
def materialize_notification_envelopes(
    effect: DeferredEffectRead,
) -> NotificationMaterializationResult:
    event_id = UUID(str(effect.payload_json["event_id"]))
    return materialize_event(get_materialize_db(), event_id)
