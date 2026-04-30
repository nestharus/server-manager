from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.scope import ScopeKind

NotificationChannel = Literal["dm", "thread", "designated_channel"]
NotificationGrouping = Literal["per_event", "per_root_cause"]
NotificationDeliveryStatus = Literal[
    "pending",
    "delivered_in_flight",
    "delivered",
    "skipped",
    "failed",
]


class _NotificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NotificationTrigger(_NotificationModel):
    event_type: str = Field(min_length=1)
    payload_filters: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value.endswith(".*"):
            prefix = value[:-2]
            if not prefix or prefix.endswith("."):
                raise ValueError("wildcard event_type must end with a non-empty prefix")
            return value
        if "*" in value:
            raise ValueError(
                "event_type wildcards are only allowed as a trailing .* suffix"
            )
        return value


class NotificationRuleCreate(_NotificationModel):
    trigger_json: NotificationTrigger = Field(alias="trigger")
    scope_kind: ScopeKind
    scope_id: str | None = None
    recipients_json: dict[str, Any] = Field(alias="recipients")
    channel: NotificationChannel
    template_json: dict[str, Any] = Field(alias="template")
    actionable: bool
    grouping: NotificationGrouping
    enabled: bool = True

    @model_validator(mode="after")
    def validate_scope_id_matches_scope_kind(self) -> "NotificationRuleCreate":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global notification rules must not set scope_id")
        if self.scope_kind in {"chapter", "member"} and self.scope_id is None:
            raise ValueError("chapter and member notification rules require scope_id")
        return self


class NotificationRulePatch(_NotificationModel):
    trigger_json: NotificationTrigger | None = Field(default=None, alias="trigger")
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    recipients_json: dict[str, Any] | None = Field(default=None, alias="recipients")
    channel: NotificationChannel | None = None
    template_json: dict[str, Any] | None = Field(default=None, alias="template")
    actionable: bool | None = None
    grouping: NotificationGrouping | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "NotificationRulePatch":
        if not self.model_fields_set:
            raise NotificationRulePatchEmptyError()
        return self


class NotificationRuleRead(_NotificationModel):
    id: UUID
    trigger_json: NotificationTrigger = Field(alias="trigger")
    scope_kind: ScopeKind
    scope_id: str | None = None
    recipients_json: dict[str, Any] = Field(alias="recipients")
    channel: NotificationChannel
    template_json: dict[str, Any] = Field(alias="template")
    actionable: bool
    grouping: NotificationGrouping
    enabled: bool
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class NotificationRuleListRead(_NotificationModel):
    items: list[NotificationRuleRead]


class NotificationTemplateEmbedField(_NotificationModel):
    name: str
    value: str
    inline: bool = False


class NotificationTemplateEmbed(_NotificationModel):
    title: str | None = None
    description: str | None = None
    url: str | None = None
    color: int | None = None
    fields: list[NotificationTemplateEmbedField] = Field(default_factory=list)


class NotificationTemplate(_NotificationModel):
    title: str = ""
    body: str = ""
    embed: NotificationTemplateEmbed | None = None


class DiscordEmbedFieldRead(_NotificationModel):
    name: str
    value: str
    inline: bool = False


class DiscordEmbedRead(_NotificationModel):
    title: str | None = None
    description: str | None = None
    url: str | None = None
    color: int | None = None
    fields: list[DiscordEmbedFieldRead] = Field(default_factory=list)


class NotificationEventDraft(_NotificationModel):
    event_type: str = Field(min_length=1)
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    payload_json: dict[str, Any]


class NotificationEventRead(_NotificationModel):
    id: UUID
    event_type: str
    correlation_id: UUID
    causation_id: UUID | None = None
    scope_kind: ScopeKind | None = None
    scope_id: str | None = None
    payload: dict[str, Any]
    created_at: datetime


class NotificationEnvelopeRead(_NotificationModel):
    id: UUID
    rule_id: UUID
    rule_version: int = Field(ge=1)
    source_event_id: UUID
    root_correlation_id: UUID
    causation_id: UUID | None = None
    grouping: NotificationGrouping
    recipient_key: str = Field(min_length=1)
    recipient_discord_id: str | None = None
    recipient_display: str = Field(min_length=1)
    channel: NotificationChannel
    destination_channel_id: str | None = None
    template_snapshot_json: dict[str, Any]
    rendered_title: str
    rendered_body: str
    rendered_embed_json: DiscordEmbedRead | None = None
    actionable: bool
    delivery_status: NotificationDeliveryStatus
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    lease_until: datetime | None = None
    attempts: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    last_error_json: dict[str, Any] | None = None
    discord_message_id: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NotificationMaterializationResult(_NotificationModel):
    event_id: UUID
    created_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    delivery_effect_count: int = Field(ge=0)
    envelope_ids: list[UUID] = Field(default_factory=list)


class NotificationDeliveryCommand(_NotificationModel):
    envelope: NotificationEnvelopeRead


class NotificationDeliveryResult(_NotificationModel):
    envelope_id: UUID
    delivery_status: NotificationDeliveryStatus = "delivered"
    discord_message_id: str | None = None
    delivered_at: datetime | None = None
    noop: bool = False


class NotificationRuleNotFoundError(Exception):
    def __init__(self, rule_id: UUID) -> None:
        self.rule_id = rule_id
        super().__init__(f"notification rule {rule_id} was not found")


class NotificationRulePatchEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("notification rule patch requires at least one field")


class UnsupportedNotificationTriggerError(Exception):
    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"unsupported notification trigger: {event_type}")


class NotificationRuleVersionError(Exception):
    def __init__(
        self, rule_id: UUID, expected_version: int, current_version: int
    ) -> None:
        self.rule_id = rule_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"stale notification rule version for {rule_id}: "
            f"expected={expected_version} current={current_version}"
        )


class TemplateRenderError(Exception):
    def __init__(self, missing_key: str) -> None:
        self.missing_key = missing_key
        super().__init__(f"template missing key: {missing_key}")


class NotificationDeliveryError(Exception):
    def __init__(self, message: str, *, definitive_failure: bool) -> None:
        self.definitive_failure = definitive_failure
        super().__init__(message)


class AmbiguousNotificationDeliveryError(NotificationDeliveryError):
    def __init__(self, message: str) -> None:
        super().__init__(message, definitive_failure=False)


__all__ = [
    "AmbiguousNotificationDeliveryError",
    "DiscordEmbedFieldRead",
    "DiscordEmbedRead",
    "NotificationChannel",
    "NotificationDeliveryCommand",
    "NotificationDeliveryError",
    "NotificationDeliveryResult",
    "NotificationDeliveryStatus",
    "NotificationEnvelopeRead",
    "NotificationEventDraft",
    "NotificationEventRead",
    "NotificationGrouping",
    "NotificationMaterializationResult",
    "NotificationTemplate",
    "NotificationTemplateEmbed",
    "NotificationTemplateEmbedField",
    "NotificationRuleCreate",
    "NotificationRuleListRead",
    "NotificationRuleNotFoundError",
    "NotificationRulePatch",
    "NotificationRulePatchEmptyError",
    "NotificationRuleRead",
    "NotificationRuleVersionError",
    "NotificationTrigger",
    "TemplateRenderError",
    "UnsupportedNotificationTriggerError",
]
