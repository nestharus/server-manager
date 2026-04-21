from __future__ import annotations

from app.contracts.tickets import SlaTriggerRead
from app.repositories.db import PostgresDatabase
from app.services.ticket_sla import evaluate_ticket_sla

_DB: PostgresDatabase | None = None


def configure_ticket_sla(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_ticket_sla_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def ticket_sla_worker_tick(*, worker_id: str = "sla-worker") -> list[SlaTriggerRead]:
    return evaluate_ticket_sla(get_ticket_sla_db(), worker_id=worker_id)
