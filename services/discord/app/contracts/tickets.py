from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _TicketCommandModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketOpenCommand(_TicketCommandModel):
    category_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    subject_discord_user_id: str | None = None


class TicketTransitionCommand(_TicketCommandModel):
    ticket_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    to_state: str = Field(min_length=1)
    reason: str | None = None
    resolution: str | None = None
    owner_id: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None


__all__ = ["TicketOpenCommand", "TicketTransitionCommand"]
