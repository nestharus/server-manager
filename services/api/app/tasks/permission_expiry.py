from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.contracts.permissions import PermissionExpirySweepResult
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.permissions import PermissionsRepository
from app.services.mutations import mutate_entity
from app.services.permissions import (
    PERMISSION_EXPIRER_ACTOR_ID,
    PermissionsService,
)


logger = logging.getLogger(__name__)

PERMISSION_EXPIRY_BATCH_SIZE: int = 50

_DB: PostgresDatabase | None = None


def configure_permission_expiry(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_permission_expiry_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def _expirer_service_actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="service", actor_id=PERMISSION_EXPIRER_ACTOR_ID)


def _root_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def permission_expiry_worker_tick(
    *,
    now: datetime | None = None,
    batch_size: int | None = None,
) -> PermissionExpirySweepResult | None:
    existing_ctx = get_current_audit_context()
    ambient = (
        use_audit_context(_root_audit_context())
        if existing_ctx is None
        else nullcontext()
    )
    with ambient:
        try:
            task_db = get_permission_expiry_db()
            repo = PermissionsRepository(db=task_db)
            service = PermissionsService(
                permissions_repo=repo,
                mutations_callable=partial(mutate_entity, db=task_db),
            )
            return service.expire_temporary_permission_intents(
                actor=_expirer_service_actor(),
                now=now or datetime.now(tz=UTC),
                batch_size=batch_size or PERMISSION_EXPIRY_BATCH_SIZE,
                source="worker_sweep",
            )
        except StaleMutationError:
            logger.debug("permission expiry: OCC conflict, retry next tick")
            return None
        except Exception:
            logger.exception("permission expiry worker tick failed")
            return None
