from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.ticket_categories import (
    RoutingScope,
    TicketPrivacyLevel,
    TicketSlaConsequence,
    TicketSlaRules,
    TicketStateMachine,
)
from app.contracts.ticket_messages import TicketMessageAppendRequest, TicketMessageRead

TicketPriority = Literal["low", "normal", "high", "urgent"]


class _TicketModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketCategorySnapshotRead(_TicketModel):
    schema_version: int
    category_id: UUID
    name: str
    category_version: int = Field(ge=1)
    routing_scope: RoutingScope
    privacy_level: TicketPrivacyLevel
    state_machine: TicketStateMachine
    sla_rules: TicketSlaRules


class TicketCreate(_TicketModel):
    category_id: UUID
    reporter_id: str | None = None
    subject_id: str | None = None
    priority: TicketPriority | None = None
    client_ticket_id: str | None = None
    initial_message: TicketMessageAppendRequest
    originating_actor_kind: Literal["user", "service"]
    originating_actor_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_originating_actor_id(self) -> "TicketCreate":
        if self.reporter_id is not None and not self.reporter_id.strip():
            raise ValueError("reporter_id must not be blank")
        if not self.originating_actor_id.strip():
            raise ValueError("originating_actor_id must not be blank")
        return self


class TicketTransitionRequest(_TicketModel):
    action: str = Field(min_length=1, max_length=64)
    to_state: str = Field(min_length=1, max_length=64)
    reason: str | None = None
    resolution: str | None = None
    owner_id: str | None = None
    priority: TicketPriority | None = None
    originating_actor_kind: Literal["user", "service"]
    originating_actor_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_originating_actor_id(self) -> "TicketTransitionRequest":
        if not self.originating_actor_id.strip():
            raise ValueError("originating_actor_id must not be blank")
        return self


class SlaThresholdRead(_TicketModel):
    elapsed_seconds: int = Field(gt=0)
    consequence: TicketSlaConsequence
    target_state: str | None = None


class SlaTriggerRead(_TicketModel):
    id: UUID
    ticket_id: UUID
    rule_key: str
    threshold_seconds: int
    consequence: TicketSlaConsequence
    target_state: str | None
    state: str
    state_entered_at: datetime
    elapsed_seconds: int
    applied_at: datetime
    effect_summary: dict[str, Any]


class TicketRead(_TicketModel):
    id: UUID
    category_id: UUID
    category_version: int = Field(ge=1)
    category_snapshot: TicketCategorySnapshotRead
    reporter_id: str
    subject_id: str | None = None
    state: str
    priority: TicketPriority
    owner_id: str | None = None
    resolution: str | None = None
    terminal_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class TicketCreateRead(_TicketModel):
    ticket: TicketRead
    initial_message: TicketMessageRead


class TicketNotFoundError(Exception):
    def __init__(self, ticket_id: UUID) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"ticket {ticket_id} was not found")


class DuplicateTicketCreateError(Exception):
    def __init__(
        self,
        ticket: TicketRead,
        initial_message: TicketMessageRead,
    ) -> None:
        self.ticket = ticket
        self.initial_message = initial_message
        super().__init__(f"ticket {ticket.id} already exists for client_ticket_id")


class InvalidTicketTransitionError(Exception):
    def __init__(
        self,
        *,
        ticket_id: UUID,
        from_state: str,
        action: str,
        to_state: str,
    ) -> None:
        self.ticket_id = ticket_id
        self.from_state = from_state
        self.action = action
        self.to_state = to_state
        super().__init__(
            f"invalid ticket transition for {ticket_id}: "
            f"{from_state} --{action}--> {to_state}"
        )


class TicketTransitionReasonRequiredError(Exception):
    def __init__(self, *, from_state: str, action: str, to_state: str) -> None:
        self.from_state = from_state
        self.action = action
        self.to_state = to_state
        super().__init__(f"transition {from_state} --{action}--> {to_state} requires reason")


class TicketTransitionResolutionRequiredError(Exception):
    def __init__(self, *, from_state: str, action: str, to_state: str) -> None:
        self.from_state = from_state
        self.action = action
        self.to_state = to_state
        super().__init__(
            f"transition {from_state} --{action}--> {to_state} requires resolution"
        )


class TicketTransitionOwnerChangeForbiddenError(Exception):
    def __init__(self, *, from_state: str, action: str, to_state: str) -> None:
        self.from_state = from_state
        self.action = action
        self.to_state = to_state
        super().__init__(
            f"transition {from_state} --{action}--> {to_state} forbids owner changes"
        )


class TicketTransitionPriorityChangeForbiddenError(Exception):
    def __init__(self, *, from_state: str, action: str, to_state: str) -> None:
        self.from_state = from_state
        self.action = action
        self.to_state = to_state
        super().__init__(
            f"transition {from_state} --{action}--> {to_state} forbids priority changes"
        )


__all__ = [
    "DuplicateTicketCreateError",
    "InvalidTicketTransitionError",
    "SlaThresholdRead",
    "SlaTriggerRead",
    "TicketCategorySnapshotRead",
    "TicketCreate",
    "TicketCreateRead",
    "TicketNotFoundError",
    "TicketPriority",
    "TicketRead",
    "TicketTransitionOwnerChangeForbiddenError",
    "TicketTransitionPriorityChangeForbiddenError",
    "TicketTransitionReasonRequiredError",
    "TicketTransitionRequest",
    "TicketTransitionResolutionRequiredError",
]
