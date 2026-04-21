from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.contracts.notifications import (
    NotificationDeliveryCommand,
    NotificationDeliveryError,
    NotificationDeliveryResult,
)


def envelope_nonce(envelope_id: UUID) -> str:
    encoded = base64.b32encode(envelope_id.bytes).decode("ascii").rstrip("=")
    return encoded[:25]


def _message_content(command: NotificationDeliveryCommand) -> str:
    title = command.envelope.rendered_title.strip()
    body = command.envelope.rendered_body.strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body


async def _send_message(target: Any, *, content: str, nonce: str) -> Any:
    return await target.send(
        content=content,
        nonce=nonce,
        enforce_nonce=True,
    )


async def deliver_notification(
    command: NotificationDeliveryCommand,
    *,
    bot: Any,
) -> NotificationDeliveryResult:
    envelope = command.envelope
    nonce = envelope_nonce(envelope.id)
    content = _message_content(command)
    try:
        if envelope.channel == "dm":
            if envelope.recipient_discord_id is None:
                raise NotificationDeliveryError(
                    "recipient_discord_id is required for dm notifications",
                    definitive_failure=True,
                )
            try:
                recipient_id = int(envelope.recipient_discord_id)
            except ValueError as error:
                raise NotificationDeliveryError(
                    "recipient_discord_id must be numeric for dm notifications",
                    definitive_failure=True,
                ) from error
            user = await bot.fetch_user(recipient_id)
            dm_channel = getattr(user, "dm_channel", None)
            if dm_channel is None:
                dm_channel = await user.create_dm()
            message = await _send_message(dm_channel, content=content, nonce=nonce)
        elif envelope.channel == "designated_channel":
            if not envelope.destination_channel_id:
                raise NotificationDeliveryError(
                    "destination_channel_id is required for designated_channel notifications",
                    definitive_failure=True,
                )
            try:
                destination_channel_id = int(envelope.destination_channel_id)
            except ValueError as error:
                raise NotificationDeliveryError(
                    "destination_channel_id must be numeric for designated_channel notifications",
                    definitive_failure=True,
                ) from error
            channel = await bot.fetch_channel(destination_channel_id)
            message = await _send_message(channel, content=content, nonce=nonce)
        else:
            raise NotificationDeliveryError(
                "thread delivery is out of scope for SLICE-015",
                definitive_failure=True,
            )
    except NotificationDeliveryError:
        raise
    except Exception as error:
        raise NotificationDeliveryError(
            str(error) or error.__class__.__name__,
            definitive_failure=False,
        ) from error
    return NotificationDeliveryResult(
        envelope_id=envelope.id,
        delivery_status="delivered",
        discord_message_id=str(getattr(message, "id", "")) or None,
        delivered_at=datetime.now(UTC),
        noop=False,
    )
