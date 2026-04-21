from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


OriginatingActorKind = Literal["user", "service"]


class _TrustModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustSignalsInput(_TrustModel):
    discord_account_age_days: int = Field(ge=0)
    has_avatar: bool
    has_verified_badge: bool
    account_flags: list[str] = Field(default_factory=list)
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)


class TrustProfileRead(_TrustModel):
    member_id: UUID
    score: int = Field(ge=0, le=100)
    tier: str = Field(min_length=1)
    signals: dict[str, Any]
    policy_version_id: UUID
    version: int = Field(ge=1)


class TrustProfileNotFoundError(Exception):
    def __init__(self, member_id: UUID) -> None:
        self.member_id = member_id
        super().__init__(f"trust profile for member {member_id} was not found")


class NoTrustPolicyConfiguredError(Exception):
    def __init__(self) -> None:
        super().__init__("no trust policy is configured")


class InvalidTrustPolicyError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"invalid trust policy: {reason}")


__all__ = [
    "InvalidTrustPolicyError",
    "NoTrustPolicyConfiguredError",
    "OriginatingActorKind",
    "TrustProfileNotFoundError",
    "TrustProfileRead",
    "TrustSignalsInput",
]
