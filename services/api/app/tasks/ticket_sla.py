from __future__ import annotations

from functools import partial

from app.contracts.tickets import SlaTriggerRead
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.notification_events import NotificationEventsRepository
from app.repositories.ticket_categories import TicketCategoriesRepository
from app.repositories.ticket_messages import TicketMessagesRepository
from app.repositories.ticket_sla import TicketSlaRepository
from app.repositories.tickets import TicketsRepository
from app.services.mutations import mutate_entity
from app.services.notification_events import NotificationEventsService
from app.services.ticket_messages import TicketMessagesService
from app.services.ticket_sla import TicketSlaService
from app.services.tickets import TicketsService

_DB: PostgresDatabase | None = None


def configure_ticket_sla(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_ticket_sla_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def _build_ticket_sla_service(db: PostgresDatabase) -> TicketSlaService:
    tickets_repo = TicketsRepository(db)
    ticket_messages_repo = TicketMessagesRepository(db)
    ticket_messages_service = TicketMessagesService(
        tickets_repo=tickets_repo,
        ticket_messages_repo=ticket_messages_repo,
    )
    tickets_service = TicketsService(
        tickets_repo=tickets_repo,
        ticket_categories_repo=TicketCategoriesRepository(db),
        ticket_messages_repo=ticket_messages_repo,
        ticket_messages_service=ticket_messages_service,
        mutations_callable=partial(mutate_entity, db=db),
    )
    return TicketSlaService(
        ticket_sla_repo=TicketSlaRepository(db),
        tickets_service=tickets_service,
        notification_events_service=NotificationEventsService(
            notification_events_repo=NotificationEventsRepository(db),
            deferred_effects_repo=DeferredEffectsRepository(db),
            mutations_callable=partial(mutate_entity, db=db),
        ),
    )


def ticket_sla_worker_tick() -> list[SlaTriggerRead]:
    return _build_ticket_sla_service(get_ticket_sla_db()).evaluate_ticket_sla()
