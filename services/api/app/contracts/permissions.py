from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.contracts.scope import ScopeKind


def _validate_decimal_bit_string(value: str) -> str:
    if not value:
        raise ValueError("decimal-digit string may not be empty")
    if not value.isascii() or not value.isdigit():
        raise ValueError("expected ASCII decimal digits only")
    if len(value) > 1 and value.startswith("0"):
        raise ValueError("decimal-digit string may not contain leading zeros")
    return value


DecimalBitString = Annotated[str, AfterValidator(_validate_decimal_bit_string)]

PermissionIntentKind: TypeAlias = Literal["guild_role", "channel_role"]
PermissionDriftStatus: TypeAlias = Literal[
    "detected",
    "acknowledged",
    "reconciled",
    "accepted",
]


class _PermissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("scope_id", "channel_id", mode="before", check_fields=False)
    @classmethod
    def _reject_empty_optional_identifiers(cls, value: Any) -> Any:
        if value == "":
            raise ValueError("optional identifiers must be non-empty when set")
        return value


class _PermissionIntentBase(_PermissionModel):
    id: UUID
    scope_kind: ScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_temporal_shape(self) -> "_PermissionIntentBase":
        if self.temporary and self.expires_at is None:
            raise ValueError("temporary permission intents require expires_at")
        if not self.temporary and self.expires_at is not None:
            raise ValueError("non-temporary permission intents forbid expires_at")
        return self


class GuildRolePermissionIntent(_PermissionIntentBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString


class ChannelRolePermissionIntent(_PermissionIntentBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString


_PermissionIntentReadUnion = Annotated[
    GuildRolePermissionIntent | ChannelRolePermissionIntent,
    Field(discriminator="kind"),
]
_permission_intent_read_adapter = TypeAdapter(_PermissionIntentReadUnion)


class _PermissionIntentNamespace:
    _adapter: ClassVar[TypeAdapter[Any]]

    @classmethod
    def model_validate(cls, value: Any) -> Any:
        return cls._adapter.validate_python(value)

    @classmethod
    def model_validate_json(cls, value: str | bytes | bytearray) -> Any:
        return cls._adapter.validate_json(value)


class PermissionIntentRead(_PermissionIntentNamespace):
    _adapter = _permission_intent_read_adapter


class _PermissionIntentCreateBase(_PermissionModel):
    scope_kind: ScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_temporal_shape(self) -> "_PermissionIntentCreateBase":
        if self.temporary and self.expires_at is None:
            raise ValueError("temporary permission intents require expires_at")
        if not self.temporary and self.expires_at is not None:
            raise ValueError("non-temporary permission intents forbid expires_at")
        return self


class GuildRolePermissionIntentCreate(_PermissionIntentCreateBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString


class ChannelRolePermissionIntentCreate(_PermissionIntentCreateBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString


_PermissionIntentCreateUnion = Annotated[
    GuildRolePermissionIntentCreate | ChannelRolePermissionIntentCreate,
    Field(discriminator="kind"),
]


class PermissionIntentCreate(_PermissionIntentNamespace):
    _adapter = TypeAdapter(_PermissionIntentCreateUnion)


class PermissionIntentUpdate(_PermissionModel):
    reason: str | None = None
    temporary: bool | None = None
    expires_at: datetime | None = None
    permission_bits: DecimalBitString | None = None
    allow_bits: DecimalBitString | None = None
    deny_bits: DecimalBitString | None = None


class PermissionDriftRead(_PermissionModel):
    id: UUID
    permission_intent_id: UUID | None = None
    intent_version: int | None = Field(default=None, ge=1)
    actual_bits: DecimalBitString | None = None
    actual_allow_bits: DecimalBitString | None = None
    actual_deny_bits: DecimalBitString | None = None
    intended_bits: DecimalBitString | None = None
    intended_allow_bits: DecimalBitString | None = None
    intended_deny_bits: DecimalBitString | None = None
    status: PermissionDriftStatus
    detected_at: datetime

    @model_validator(mode="after")
    def validate_intent_anchor(self) -> "PermissionDriftRead":
        if (self.permission_intent_id is None) != (self.intent_version is None):
            raise ValueError(
                "permission_intent_id and intent_version must be both set or both null"
            )
        return self


class InvalidPermissionIntentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = [
    "ChannelRolePermissionIntent",
    "DecimalBitString",
    "GuildRolePermissionIntent",
    "InvalidPermissionIntentError",
    "PermissionDriftRead",
    "PermissionIntentCreate",
    "PermissionIntentRead",
    "PermissionIntentUpdate",
    "_PermissionIntentBase",
    "_validate_decimal_bit_string",
]
