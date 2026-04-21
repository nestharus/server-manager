from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

from app.contracts.scope import ScopeKind


OriginatingActorKind = Literal["user", "service"]
TrustSignalActorKind = Literal["user", "service"]


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
    config_version: int = Field(ge=1)
    version: int = Field(ge=1)


class TrustSignalScope(_TrustModel):
    scope_kind: ScopeKind
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global trust signal scope must not include scope_id")
        if self.scope_kind in {"chapter", "member"} and not self.scope_id:
            raise ValueError("chapter/member trust signal scope requires scope_id")
        return self

    def to_persisted_json(self) -> dict[str, str]:
        if self.scope_kind == "global":
            return {"scope_kind": "global"}
        if self.scope_id is None:
            raise ValueError("scoped trust signal requires scope_id")
        return {"scope_kind": self.scope_kind, "scope_id": self.scope_id}


class TrustSignalCreate(_TrustModel):
    member_id: UUID
    signal_type: str = Field(min_length=1)
    scope: TrustSignalScope
    value: dict[str, Any]
    observed_at: AwareDatetime
    expires_at: AwareDatetime | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: dict[str, Any]) -> dict[str, Any]:
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, (int, float)):
            raise ValueError("trust signal value must include numeric schema_version")
        return value

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        return self


class TrustSignalRead(_TrustModel):
    id: UUID
    member_id: UUID
    signal_type: str
    scope: TrustSignalScope
    value: dict[str, Any]
    source_actor_kind: TrustSignalActorKind
    source_actor_id: str
    observed_at: datetime
    expires_at: datetime | None
    created_at: datetime


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


class InvalidTrustSignalScopeError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"invalid trust signal scope: {reason}")


class InvalidTrustSignalActorError(Exception):
    def __init__(self) -> None:
        super().__init__("trust signal source actor must be a user or service")


class TrustRecomputeConflictError(Exception):
    def __init__(self) -> None:
        super().__init__("trust profile changed during recompute")


__all__ = [
    "InvalidTrustPolicyError",
    "InvalidTrustSignalActorError",
    "InvalidTrustSignalScopeError",
    "NoTrustPolicyConfiguredError",
    "OriginatingActorKind",
    "TrustProfileNotFoundError",
    "TrustProfileRead",
    "TrustRecomputeConflictError",
    "TrustSignalActorKind",
    "TrustSignalCreate",
    "TrustSignalRead",
    "TrustSignalScope",
    "TrustSignalsInput",
]
