from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _OnboardingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemberJoinSignals(_OnboardingModel):
    discord_account_age_days: int = Field(ge=0)
    has_avatar: bool
    has_verified_badge: bool
    account_flags: list[str] = Field(default_factory=list)


class MemberJoinEvent(_OnboardingModel):
    discord_user_id: str = Field(min_length=1)
    joined_at: datetime
    signals: MemberJoinSignals
    originating_actor_kind: Literal["user"] = "user"
    originating_actor_id: str = Field(min_length=1)


class MemberJoinOutcomeRead(_OnboardingModel):
    member: dict[str, Any]
    trust: dict[str, Any]
    intake_required: bool


__all__ = [
    "MemberJoinEvent",
    "MemberJoinOutcomeRead",
    "MemberJoinSignals",
]
