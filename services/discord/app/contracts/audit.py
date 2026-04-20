from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CorrelationHeadersRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    x_correlation_id: UUID
    x_causation_id: UUID | None = None


class AuditContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: UUID
    causation_id: UUID | None = None
    headers: CorrelationHeadersRead


__all__ = ["AuditContextRead", "CorrelationHeadersRead"]
