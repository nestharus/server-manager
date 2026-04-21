from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InteractionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    interaction_id: str = Field(min_length=1)
    correlation_id: UUID
    causation_id: UUID | None = None
    actor_kind: Literal["discord_user"]
    actor_id: str = Field(min_length=1)
    guild_id: str | None = None
    command_name: str = Field(min_length=1)
    arguments: dict[str, Any]
    ack_deferred: Callable[[], Awaitable[None]] | None = Field(
        default=None,
        exclude=True,
    )


class InteractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    success: bool
    response_text: str | None = None
    ephemeral: bool = True


class InteractionHandler(Protocol):
    async def __call__(self, envelope: InteractionEnvelope) -> InteractionResult: ...


class DuplicateHandlerError(Exception):
    def __init__(self, command_name: str) -> None:
        self.command_name = command_name
        super().__init__(f"handler already registered for {command_name}")


class HandlerNotFoundError(Exception):
    def __init__(self, command_name: str) -> None:
        self.command_name = command_name
        super().__init__(f"no handler registered for {command_name}")


__all__ = [
    "DuplicateHandlerError",
    "HandlerNotFoundError",
    "InteractionEnvelope",
    "InteractionHandler",
    "InteractionResult",
]
