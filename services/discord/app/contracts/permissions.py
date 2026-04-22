from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
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

DiscordPermissionScopeKind: TypeAlias = Literal["global", "chapter"]
DiscordPermissionKind: TypeAlias = Literal["guild_role", "channel_role"]
DiscordRunStatus: TypeAlias = Literal[
    "requested",
    "snapshot_submitted",
    "reconciled",
    "failed",
]


class _DiscordPermissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscordReconciliationRunCreate(_DiscordPermissionModel):
    scope_kind: DiscordPermissionScopeKind
    scope_id: str | None = None
    originating_actor_kind: str
    originating_actor_id: str

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "DiscordReconciliationRunCreate":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self


class DiscordReconciliationRunRead(_DiscordPermissionModel):
    id: UUID
    scope_kind: DiscordPermissionScopeKind
    scope_id: str | None = None
    requested_by_kind: str
    requested_by_id: str
    requested_at: datetime
    snapshot_submitted_at: datetime | None = None
    reconciled_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    status: DiscordRunStatus
    drift_ids: list[UUID] = Field(default_factory=list)


class _DiscordSnapshotBase(_DiscordPermissionModel):
    role_id: str = Field(min_length=1)


class DiscordGuildRoleSnapshotEntry(_DiscordSnapshotBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString


class DiscordChannelRoleSnapshotEntry(_DiscordSnapshotBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString


DiscordPermissionSnapshotEntry = Annotated[
    DiscordGuildRoleSnapshotEntry | DiscordChannelRoleSnapshotEntry,
    Field(discriminator="kind"),
]


class DiscordReconciliationSnapshotRequest(_DiscordPermissionModel):
    entries: list[DiscordPermissionSnapshotEntry] = Field(default_factory=list)

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


__all__ = [
    "DecimalBitString",
    "DiscordChannelRoleSnapshotEntry",
    "DiscordGuildRoleSnapshotEntry",
    "DiscordPermissionKind",
    "DiscordPermissionScopeKind",
    "DiscordPermissionSnapshotEntry",
    "DiscordReconciliationRunCreate",
    "DiscordReconciliationRunRead",
    "DiscordReconciliationSnapshotRequest",
    "DiscordRunStatus",
]
