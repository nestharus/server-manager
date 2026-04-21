from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RosterStatus = Literal["active", "on_leave", "under_review", "removed"]


class _RosterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RosterSyncEvent(_RosterModel):
    roster_entry_id: str = Field(min_length=1)
    roster_entry_version: int = Field(ge=1)
    transition_id: str = Field(min_length=1)
    chapter_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    member_discord_user_id: str = Field(min_length=1)
    chapter_role_name: str = Field(min_length=1)
    chapter_discord_role_id: str | None = None
    chapter_discord_resources: dict[str, Any]
    status: RosterStatus
    originating_actor_kind: Literal["user", "service"] = "user"
    originating_actor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    correlation_id: str | None = None
    ack_deferred: Any | None = None


class RosterSyncResult(_RosterModel):
    roster_entry_id: str
    transition_id: str
    applied_role_ids: list[str]
    skipped_role_ids: list[str]
    failure_recorded: bool = False
    deferred_effect_id: str | None = None


__all__ = [
    "RosterStatus",
    "RosterSyncEvent",
    "RosterSyncResult",
]
