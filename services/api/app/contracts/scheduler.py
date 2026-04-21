from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ScheduledJobStatus = Literal["queued", "claimed", "completed", "failed", "abandoned"]
ConsequenceLevel = Literal["safe", "consequential"]
PreconditionState = Literal["unchecked", "valid", "invalid"]
DeferredEffectStatus = Literal["queued", "claimed", "completed", "failed", "skipped"]


class ScheduledJobCreate(BaseModel):
    job_key: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    handler_name: str = Field(min_length=1)
    next_run_at: datetime
    correlation_id: UUID | None = None
    max_attempts: int = Field(gt=0)


class ScheduledJobRead(BaseModel):
    job_key: str
    subsystem: str
    handler_name: str
    next_run_at: datetime
    status: ScheduledJobStatus
    attempts: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    correlation_id: UUID
    created_at: datetime
    updated_at: datetime


class DeferredEffectCreate(BaseModel):
    subsystem: str = Field(min_length=1)
    effect_type: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_json: dict[str, Any]
    consequence_level: ConsequenceLevel
    correlation_id: UUID | None = None


class DeferredEffectRead(BaseModel):
    id: UUID
    subsystem: str
    effect_type: str
    idempotency_key: str
    payload_json: dict[str, Any]
    consequence_level: ConsequenceLevel
    precondition_state: PreconditionState
    status: DeferredEffectStatus
    attempts: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    correlation_id: UUID
    created_at: datetime
    updated_at: datetime


class DegradedStateSummaryRead(BaseModel):
    subsystem: str
    pending_effect_count: int = Field(ge=0)
    scheduled_job_count: int = Field(ge=0)
    stuck_in_flight_envelopes: int | None = Field(default=None, ge=0)
    oldest_pending_at: datetime | None = None


class SchedulerHandlerConflictError(Exception):
    def __init__(self, handler_name: str) -> None:
        self.handler_name = handler_name
        super().__init__(f"scheduler handler already registered: {handler_name}")


class InvalidPreconditionStateTransitionError(Exception):
    def __init__(self, effect_id: UUID, current_state: str) -> None:
        self.effect_id = effect_id
        self.current_state = current_state
        super().__init__(
            f"invalid precondition transition for deferred effect {effect_id}: "
            f"current_state={current_state}"
        )


__all__ = [
    "ConsequenceLevel",
    "DeferredEffectCreate",
    "DeferredEffectRead",
    "DeferredEffectStatus",
    "DegradedStateSummaryRead",
    "InvalidPreconditionStateTransitionError",
    "PreconditionState",
    "ScheduledJobCreate",
    "ScheduledJobRead",
    "ScheduledJobStatus",
    "SchedulerHandlerConflictError",
]
