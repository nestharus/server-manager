from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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
    removal_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class RosterEntryCreate(_RosterModel):
    chapter_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    role_id: UUID


class RosterEntryTransitionRequest(_RosterModel):
    to_status: RosterStatus
    to_role_id: UUID | None = None
    reason: str = Field(min_length=1)
    removal_metadata: dict[str, Any] = Field(default_factory=dict)
    originating_actor_kind: Literal["user", "service"] = "user"
    originating_actor_id: str = Field(min_length=1)


class RosterSyncFailureRequest(_RosterModel):
    transition_id: UUID
    reason: str = Field(min_length=1)
    member_discord_user_id: str | None = None
    operation: Literal["add_roles", "remove_roles", "resolve_member", "resolve_role"]
    failed_at_step: str = Field(min_length=1)
    desired_discord_role_ids: list[str] = Field(default_factory=list)
    error_type: str | None = None
    originating_actor_kind: Literal["user", "service"] = "service"
    originating_actor_id: str = Field(min_length=1)


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


class RosterEntryNotFoundError(Exception):
    def __init__(self, entry_id: UUID) -> None:
        self.entry_id = entry_id
        super().__init__(f"roster entry {entry_id} was not found")


class RosterRoleChapterMismatchError(Exception):
    def __init__(self, role_id: UUID, chapter_id: str) -> None:
        self.role_id = role_id
        self.chapter_id = chapter_id
        super().__init__(f"chapter role {role_id} does not belong to {chapter_id}")


class RosterDuplicateCurrentEntryError(Exception):
    def __init__(self, chapter_id: str, member_id: str) -> None:
        self.chapter_id = chapter_id
        self.member_id = member_id
        super().__init__(
            f"current roster entry already exists for {chapter_id}/{member_id}"
        )


__all__ = [
    "InvalidRosterStatusTransitionError",
    "RosterDuplicateCurrentEntryError",
    "RosterEntryCreate",
    "RosterEntryNotFoundError",
    "RosterEntryRead",
    "RosterEntryTransitionRequest",
    "RosterRoleNotFoundError",
    "RosterRoleChapterMismatchError",
    "RosterStatus",
    "RosterSyncFailureRequest",
]
