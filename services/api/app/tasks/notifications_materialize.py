from __future__ import annotations

from uuid import UUID

from functools import partial

from app.contracts.notifications import NotificationMaterializationResult
from app.contracts.scheduler import DeferredEffectRead
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.notification_events import NotificationEventsRepository
from app.repositories.notifications import NotificationsRepository
from app.services.mutations import mutate_entity
from app.services.notifications_materialize import NotificationsMaterializeService
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
    db = get_materialize_db()
    return NotificationsMaterializeService(
        notifications_repo=NotificationsRepository(db),
        notification_events_repo=NotificationEventsRepository(db),
        deferred_effects_repo=DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    ).materialize_event(event_id)
