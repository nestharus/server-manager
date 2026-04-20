from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActorIdentity(BaseModel):
    actor_kind: Literal["user", "service", "system"]
    actor_id: str = Field(min_length=1)


class ActorIdentityMissingError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


__all__ = ["ActorIdentity", "ActorIdentityMissingError"]
