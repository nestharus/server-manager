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


@register_scheduler_handler("notifications_materialize")
def materialize_notification_envelopes(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> NotificationMaterializationResult:
    event_id = UUID(str(effect.payload_json["event_id"]))
    return NotificationsMaterializeService(
        notifications_repo=NotificationsRepository(db),
        notification_events_repo=NotificationEventsRepository(db),
        deferred_effects_repo=DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    ).materialize_event(event_id)
