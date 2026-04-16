"""Activity/Audit Model contracts.

Pydantic models for activity actions, state changes, and aggregate heads.
These encode the specification from the Activity/Audit Model proposal
(sections 3-5).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionStatus(StrEnum):
    accepted = "accepted"
    rejected = "rejected"
    failed = "failed"
    noop = "noop"


class ActionRecord(BaseModel):
    id: int
    action_type: str
    aggregate_type: str
    aggregate_id: int
    actor_kind: str
    actor_id: str
    request_surface: str
    request_json: dict[str, Any]
    status: ActionStatus
    reason_text: str | None = None
    recorded_at: datetime


class StateChangeRecord(BaseModel):
    id: int
    action_id: int
    aggregate_type: str
    aggregate_id: int
    aggregate_seq: int = Field(ge=1)
    change_type: str
    payload_json: dict[str, Any]
    diff_json: dict[str, Any] | None = None
    recorded_at: datetime


class AggregateHead(BaseModel):
    aggregate_type: str
    aggregate_id: int
    current_seq: int = Field(ge=1)
    latest_change_id: int


__all__ = [
    "ActionStatus",
    "ActionRecord",
    "AggregateHead",
    "StateChangeRecord",
]
