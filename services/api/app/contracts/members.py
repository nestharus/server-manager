from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MemberStatus = Literal["active", "suspended", "departed"]
OriginatingActorKind = Literal["user", "service"]


class _MemberModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemberCreate(_MemberModel):
    discord_user_id: str = Field(min_length=1)
    joined_at: datetime
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)


class MemberRead(_MemberModel):
    id: UUID
    discord_user_id: str
    joined_at: datetime
    status: MemberStatus
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class MemberStatusPatch(_MemberModel):
    status: MemberStatus
    reason: str = Field(min_length=1)
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)


class MemberNotFoundError(Exception):
    def __init__(self, member_id: UUID | None = None, discord_user_id: str | None = None) -> None:
        self.member_id = member_id
        self.discord_user_id = discord_user_id
        if member_id is not None:
            message = f"member {member_id} was not found"
        elif discord_user_id is not None:
            message = f"member with discord_user_id {discord_user_id!r} was not found"
        else:
            message = "member was not found"
        super().__init__(message)


class InvalidMemberStatusTransitionError(Exception):
    def __init__(self, current_status: str, new_status: str) -> None:
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(
            f"invalid member status transition: {current_status} -> {new_status}"
        )


__all__ = [
    "InvalidMemberStatusTransitionError",
    "MemberCreate",
    "MemberNotFoundError",
    "MemberRead",
    "MemberStatus",
    "MemberStatusPatch",
    "OriginatingActorKind",
]
