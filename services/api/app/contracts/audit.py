from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.contracts.scope import ScopeKind


class CorrelationHeadersRead(BaseModel):
    x_correlation_id: UUID
    x_causation_id: UUID | None = None


class AuditContextRead(BaseModel):
    correlation_id: UUID
    causation_id: UUID | None = None
    headers: CorrelationHeadersRead


class AuditEntryRead(BaseModel):
    id: int
    recorded_at: datetime
    actor_kind: str
    actor_id: str
    action_type: str
    aggregate_type: str
    aggregate_id: str
    status: Literal["accepted", "rejected", "failed"]
    correlation: AuditContextRead
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    request_surface: str
    reason_text: str | None = None


__all__ = [
    "AuditContextRead",
    "AuditEntryRead",
    "CorrelationHeadersRead",
]
