from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.core.context import get_current_audit_context, use_audit_context
from app.infrastructure.ocr import OcrProviderNotConfiguredError
from app.repositories.compliance import ComplianceRepository
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.members import MembersRepository
from app.repositories.roster import RosterRepository
from app.services.compliance import ComplianceService, compliance_evaluator_actor
from app.services.mutations import mutate_entity
from app.services.roster import RosterService


logger = logging.getLogger(__name__)

_DB: PostgresDatabase | None = None


def configure_compliance_worker(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_compliance_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


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


def compliance_evaluation_worker_tick(
    db: PostgresDatabase | None = None,
    *,
    now: datetime | None = None,
):
    existing_ctx = get_current_audit_context()
    ambient = (
        use_audit_context(_root_audit_context())
        if existing_ctx is None
        else nullcontext()
    )
    with ambient:
        try:
            task_db = get_compliance_db() if db is None else db
            mutations_callable = partial(mutate_entity, db=task_db)
            compliance_repo = ComplianceRepository(db=task_db)
            roster_service = RosterService(
                roster_repo=RosterRepository(db=task_db),
                members_repo=MembersRepository(db=task_db),
                deferred_effects_repo=DeferredEffectsRepository(db=task_db),
                mutations_callable=mutations_callable,
            )
            compliance_service = ComplianceService(
                compliance_repo=compliance_repo,
                roster_service=roster_service,
                mutations_callable=mutations_callable,
            )
            return compliance_service.run_scheduled_compliance_evaluations(
                now=now or datetime.now(tz=UTC),
                actor=compliance_evaluator_actor(),
            )
        except StaleMutationError:
            logger.debug("compliance evaluation: OCC conflict, retry next tick")
            return None
        except OcrProviderNotConfiguredError:
            logger.warning("compliance evaluation worker tick skipped: OCR provider not configured")
            return None
        except Exception:
            logger.exception("compliance evaluation worker tick failed")
            return None


__all__ = ["compliance_evaluation_worker_tick", "configure_compliance_worker"]
