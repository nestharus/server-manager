from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class NotificationDeliveryCommand(_NotificationModel):
    envelope: NotificationEnvelopeRead


class NotificationDeliveryResult(_NotificationModel):
    envelope_id: UUID
    delivery_status: NotificationDeliveryStatus = "delivered"
    discord_message_id: str | None = None
    delivered_at: datetime | None = None
    noop: bool = False


class NotificationDeliveryError(Exception):
    def __init__(self, message: str, *, definitive_failure: bool) -> None:
        self.definitive_failure = definitive_failure
        super().__init__(message)


__all__ = [
    "NotificationDeliveryCommand",
    "NotificationDeliveryError",
    "NotificationDeliveryResult",
    "NotificationDeliveryStatus",
    "NotificationEnvelopeRead",
]
