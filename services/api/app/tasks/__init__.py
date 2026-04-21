from collections.abc import Callable

from app.repositories.db import PostgresDatabase
from app.services.notifications_delivery import NotificationDeliveryPort
from app.services.scheduler import register_scheduler_handler
from app.tasks.notifications_deliver import configure_notifications_deliver
from app.tasks.notifications_materialize import configure_notifications_materialize
from app.tasks.ticket_sla import configure_ticket_sla


def configure_task_runtime(
    *,
    db: PostgresDatabase,
    delivery_port_factory: Callable[[], NotificationDeliveryPort] | None = None,
) -> None:
    configure_notifications_materialize(db=db)
    configure_notifications_deliver(
        db=db,
        delivery_port_factory=delivery_port_factory,
    )
    configure_ticket_sla(db=db)


__all__ = ["NotificationDeliveryPort", "configure_task_runtime", "register_scheduler_handler"]
