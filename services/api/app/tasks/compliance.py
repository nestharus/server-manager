from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.core.context import get_current_audit_context, use_audit_context
from app.infrastructure.ocr import OcrProviderNotConfiguredError
from app.repositories.db import PostgresDatabase
from app.services.compliance import compliance_evaluator_actor, run_scheduled_compliance_evaluations


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
            return run_scheduled_compliance_evaluations(
                get_compliance_db() if db is None else db,
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
