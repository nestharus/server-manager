from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _ReadModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadModelCursorRead(_ReadModelContract):
    projection_name: str
    last_processed_id: int
    last_processed_at: datetime | None
    version: int


class OperationalOverviewRead(_ReadModelContract):
    scope_kind: Literal["global", "chapter"]
    scope_id: str | None
    open_applications_count: int
    open_tickets_count: int
    pending_deferred_effects_count: int
    permission_drift_count: int
    stale_projections: list[str]
    stale_since: datetime | None
    is_stale: bool


__all__ = ["OperationalOverviewRead", "ReadModelCursorRead"]
