from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.scope import ScopeKind


class NotificationEventDraft(BaseModel):
    event_type: str = Field(min_length=1)
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    payload_json: dict[str, Any]


class NotificationEventRead(BaseModel):
    id: UUID
    event_type: str
    correlation_id: UUID
    causation_id: UUID | None = None
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    payload: dict[str, Any]
    created_at: datetime


__all__ = [
    "NotificationEventDraft",
    "NotificationEventRead",
]
