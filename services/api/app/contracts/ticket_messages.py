from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TicketMessageVisibility = Literal["reporter_visible", "staff_only"]


class _TicketMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketMessageAppendRequest(_TicketMessageModel):
    body_markdown: str = Field(min_length=1)
    visibility: TicketMessageVisibility
    client_message_id: str | None = None
    author_actor_kind: Literal["user", "service", "system"]
    author_actor_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_author(self) -> "TicketMessageAppendRequest":
        if not self.author_actor_id.strip():
            raise ValueError("author_actor_id must not be blank")
        return self


class TicketMessageRead(_TicketMessageModel):
    id: UUID
    ticket_id: UUID
    message_seq: int = Field(ge=1)
    author_actor_kind: str
    author_actor_id: str
    visibility: TicketMessageVisibility
    body_markdown: str
    client_message_id: str | None = None
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


class TicketMessageListRead(_TicketMessageModel):
    items: list[TicketMessageRead]


class TicketMessageVisibilityError(ValueError):
    pass


class TicketMessageAppendForbiddenError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = [
    "TicketMessageAppendForbiddenError",
    "TicketMessageAppendRequest",
    "TicketMessageListRead",
    "TicketMessageRead",
    "TicketMessageVisibility",
    "TicketMessageVisibilityError",
]
