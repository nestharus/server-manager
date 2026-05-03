from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.contracts.mutations import StaleMutationError
from app.contracts.read_models import ReadModelCursorRead
from app.repositories.db import PostgresDatabase
from app.services.read_models import (
    CursorNotSeededError,
    advance_operational_overview_cursor,
)


logger = logging.getLogger(__name__)

def read_model_worker_tick(
    db: PostgresDatabase,
    *,
    now: datetime | None = None,
) -> ReadModelCursorRead | None:
    resolved_db = db
    resolved_now = now if now is not None else datetime.now(tz=UTC)
    try:
        return advance_operational_overview_cursor(
            resolved_db,
            now=resolved_now,
        )
    except StaleMutationError:
        logger.debug("read-model worker tick skipped due to OCC conflict")
        return None
    except CursorNotSeededError:
        logger.warning("read-model worker tick skipped: cursor not seeded")
        return None
    except Exception:
        logger.exception("read-model worker tick failed")
        return None


__all__ = ["read_model_worker_tick"]
