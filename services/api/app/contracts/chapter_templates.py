from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.permissions import DecimalBitString


CURRENT_TEMPLATE_SCHEMA_VERSION = 1


class _TemplateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChannelSpec(_TemplateModel):
    name: str = Field(min_length=1)
    type: Literal["text", "voice", "category"]
    topic: str | None = None


class RoleSpec(_TemplateModel):
    name: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    triggers_succession: bool


class DefaultIntentSpec(_TemplateModel):
    role_name: str = Field(min_length=1)
    kind: Literal["guild_role", "channel_role"]
    permission_bits: DecimalBitString | None = None
    allow_bits: DecimalBitString | None = None
    deny_bits: DecimalBitString | None = None
    channel_name: str | None = Field(default=None, min_length=1)
    temporary: bool
    expires_in_days: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_shape(self) -> "DefaultIntentSpec":
        if self.kind == "guild_role":
            if self.permission_bits is None:
                raise ValueError("guild_role defaults require permission_bits")
            if (
                self.allow_bits is not None
                or self.deny_bits is not None
                or self.channel_name is not None
            ):
                raise ValueError("guild_role defaults forbid channel overwrite fields")
        if self.kind == "channel_role":
            if (
                self.allow_bits is None
                or self.deny_bits is None
                or self.channel_name is None
            ):
                raise ValueError(
                    "channel_role defaults require allow_bits, deny_bits, and channel_name"
                )
            if self.permission_bits is not None:
                raise ValueError("channel_role defaults forbid permission_bits")
        if self.temporary and self.expires_in_days is None:
            raise ValueError("temporary defaults require expires_in_days")
        if not self.temporary and self.expires_in_days is not None:
            raise ValueError("non-temporary defaults forbid expires_in_days")
        return self


class ChapterTemplateRead(_TemplateModel):
    id: UUID
    name: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    channel_structure: list[ChannelSpec]
    role_structure: list[RoleSpec]
    default_permission_intents: list[DefaultIntentSpec]
    created_at: datetime


class ChapterTemplateCreate(_TemplateModel):
    name: str = Field(min_length=1)
    schema_version: int = CURRENT_TEMPLATE_SCHEMA_VERSION
    channel_structure: list[ChannelSpec]
    role_structure: list[RoleSpec]
    default_permission_intents: list[DefaultIntentSpec]

    @model_validator(mode="after")
    def validate_schema_version(self) -> "ChapterTemplateCreate":
        if self.schema_version != CURRENT_TEMPLATE_SCHEMA_VERSION:
            raise ValueError(
                "chapter templates must use the current schema version"
            )
        return self


class TemplateSchemaVersionMismatchError(Exception):
    def __init__(self, schema_version: int) -> None:
        self.schema_version = schema_version
        super().__init__(
            "chapter template schema version mismatch: "
            f"expected {CURRENT_TEMPLATE_SCHEMA_VERSION}, got {schema_version}"
        )


__all__ = [
    "CURRENT_TEMPLATE_SCHEMA_VERSION",
    "ChannelSpec",
    "ChapterTemplateCreate",
    "ChapterTemplateRead",
    "DefaultIntentSpec",
    "RoleSpec",
    "TemplateSchemaVersionMismatchError",
]
