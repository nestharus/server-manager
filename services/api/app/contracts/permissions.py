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
PermissionIntentScopeKind: TypeAlias = Literal["global", "chapter"]
PermissionDriftStatus: TypeAlias = Literal[
    "detected",
    "acknowledged",
    "reconciled",
    "accepted",
]
DriftResolutionAction: TypeAlias = Literal["acknowledge", "reconcile", "accept"]
PermissionReconciliationRunStatus: TypeAlias = Literal[
    "requested",
    "snapshot_submitted",
    "reconciled",
    "failed",
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
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "_PermissionIntentBase":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self

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
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "_PermissionIntentCreateBase":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self

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

    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    channel_id: str | None = None
    kind: PermissionIntentKind
    reconciliation_run_id: UUID | None = None

    actual_bits: DecimalBitString | None = None
    actual_allow_bits: DecimalBitString | None = None
    actual_deny_bits: DecimalBitString | None = None
    intended_bits: DecimalBitString | None = None
    intended_allow_bits: DecimalBitString | None = None
    intended_deny_bits: DecimalBitString | None = None

    status: PermissionDriftStatus
    detected_at: datetime

    resolved_by_kind: str | None = None
    resolved_by_id: str | None = None
    resolved_at: datetime | None = None
    resolution_reason: str | None = None

    @model_validator(mode="after")
    def validate_intent_anchor(self) -> "PermissionDriftRead":
        if (self.permission_intent_id is None) != (self.intent_version is None):
            raise ValueError(
                "permission_intent_id and intent_version must be both set or both null"
            )
        return self

    @model_validator(mode="after")
    def validate_variant_shape(self) -> "PermissionDriftRead":
        if self.kind == "guild_role" and self.channel_id is not None:
            raise ValueError("guild_role drift forbids channel_id")
        if self.kind == "channel_role" and self.channel_id is None:
            raise ValueError("channel_role drift requires channel_id")
        return self

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "PermissionDriftRead":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> "PermissionDriftRead":
        resolution_present = (
            self.resolved_by_kind is not None
            or self.resolved_by_id is not None
            or self.resolved_at is not None
            or self.resolution_reason is not None
        )
        if self.status in ("reconciled", "accepted"):
            if not all(
                (
                    self.resolved_by_kind,
                    self.resolved_by_id,
                    self.resolved_at,
                    self.resolution_reason,
                )
            ):
                raise ValueError("terminal drift requires full resolution metadata")
        elif resolution_present:
            raise ValueError("non-terminal drift forbids resolution metadata")
        return self


class PermissionDriftResolutionRequest(_PermissionModel):
    action: DriftResolutionAction
    reason: str = Field(min_length=1)
    resolved_by_kind: str | None = None
    resolved_by_id: str | None = None

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-blank")
        return value

    @model_validator(mode="after")
    def validate_resolved_by_pair(self) -> "PermissionDriftResolutionRequest":
        if (self.resolved_by_kind is None) != (self.resolved_by_id is None):
            raise ValueError(
                "resolved_by_kind and resolved_by_id must be supplied together "
                "or omitted together"
            )
        return self


class PermissionReconciliationRunCreate(_PermissionModel):
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    originating_actor_kind: str | None = None
    originating_actor_id: str | None = None

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "PermissionReconciliationRunCreate":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self


class PermissionReconciliationRunRead(_PermissionModel):
    id: UUID
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    requested_by_kind: str
    requested_by_id: str
    requested_at: datetime
    snapshot_submitted_at: datetime | None = None
    reconciled_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    status: PermissionReconciliationRunStatus
    drift_ids: list[UUID] = Field(default_factory=list)


class _PermissionSnapshotBase(_PermissionModel):
    role_id: str = Field(min_length=1)


class GuildRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString


class ChannelRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString


PermissionSnapshotEntry = Annotated[
    GuildRolePermissionSnapshotEntry | ChannelRolePermissionSnapshotEntry,
    Field(discriminator="kind"),
]


class ReconciliationSnapshotRequest(_PermissionModel):
    entries: list[PermissionSnapshotEntry] = Field(default_factory=list)

    @field_validator("entries")
    @classmethod
    def reject_duplicate_keys(cls, value: list[Any]) -> list[Any]:
        seen: set[tuple[str, str, str | None]] = set()
        for entry in value:
            key = (
                entry.kind,
                entry.role_id,
                getattr(entry, "channel_id", None),
            )
            if key in seen:
                raise ValueError(f"duplicate snapshot entry for {key}")
            seen.add(key)
        return value


class InvalidPermissionIntentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class PermissionIntentNotFoundError(LookupError):
    def __init__(self, intent_id: UUID) -> None:
        self.intent_id = intent_id
        super().__init__(f"permission intent {intent_id} was not found")


class PermissionDriftNotFoundError(LookupError):
    def __init__(self, drift_id: UUID) -> None:
        self.drift_id = drift_id
        super().__init__(f"permission drift {drift_id} was not found")


__all__ = [
    "ChannelRolePermissionIntent",
    "ChannelRolePermissionIntentCreate",
    "ChannelRolePermissionSnapshotEntry",
    "DecimalBitString",
    "DriftResolutionAction",
    "GuildRolePermissionIntent",
    "GuildRolePermissionIntentCreate",
    "GuildRolePermissionSnapshotEntry",
    "InvalidPermissionIntentError",
    "PermissionDriftNotFoundError",
    "PermissionDriftRead",
    "PermissionDriftResolutionRequest",
    "PermissionDriftStatus",
    "PermissionIntentCreate",
    "PermissionIntentKind",
    "PermissionIntentNotFoundError",
    "PermissionIntentRead",
    "PermissionIntentScopeKind",
    "PermissionIntentUpdate",
    "PermissionReconciliationRunCreate",
    "PermissionReconciliationRunRead",
    "PermissionReconciliationRunStatus",
    "PermissionSnapshotEntry",
    "ReconciliationSnapshotRequest",
    "_PermissionIntentBase",
    "_validate_decimal_bit_string",
]
