from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


RosterStatus = Literal["active", "on_leave", "under_review", "removed"]


class _RosterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RosterEntryRead(_RosterModel):
    id: UUID
    chapter_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    role_id: UUID
    status: RosterStatus
    created_at: datetime


class RosterEntryCreate(_RosterModel):
    chapter_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    role_id: UUID
    status: RosterStatus = "active"


class InvalidRosterStatusTransitionError(Exception):
    def __init__(self, current_status: str, new_status: str) -> None:
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(
            f"invalid roster status transition: {current_status} -> {new_status}"
        )


class RosterRoleNotFoundError(Exception):
    def __init__(self, role_id: UUID) -> None:
        self.role_id = role_id
        super().__init__(f"chapter role {role_id} was not found")


__all__ = [
    "InvalidRosterStatusTransitionError",
    "RosterEntryCreate",
    "RosterEntryRead",
    "RosterRoleNotFoundError",
    "RosterStatus",
]
