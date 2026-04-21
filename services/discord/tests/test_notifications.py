from __future__ import annotations

import base64
import importlib
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest


def _load_notifications_handler() -> Any:
    try:
        return importlib.import_module("app.handlers.notifications")
    except ModuleNotFoundError as error:
        pytest.fail(f"missing SLICE-015 Discord notification handler module: {error}")


def _expected_nonce(envelope_id: UUID) -> str:
    return base64.b32encode(envelope_id.bytes).decode("ascii").rstrip("=")[:25]


def _command(
    *,
    envelope_id: UUID,
    channel: str = "dm",
    destination_channel_id: str | None = None,
) -> Any:
    envelope = SimpleNamespace(
        id=envelope_id,
        rendered_title="Title",
        rendered_body="Body",
        recipient_discord_id="1001",
        recipient_display="1001",
        channel=channel,
        destination_channel_id=destination_channel_id,
        actionable=False,
    )
    return SimpleNamespace(envelope=envelope)


@pytest.mark.asyncio
async def test_delivery_uses_deterministic_nonce_derived_from_envelope_id() -> None:
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification", None)
    envelope_nonce = getattr(handler_module, "envelope_nonce", None)
    if deliver_notification is None:
        pytest.fail("missing Discord deliver_notification(command, *, bot) handler")
    if envelope_nonce is None:
        pytest.fail("missing envelope_nonce(envelope_id) helper")

    envelope_id = UUID("12345678-1234-5678-1234-567812345678")
    dm_channel = SimpleNamespace(
        id="dm-1",
        send=AsyncMock(return_value=SimpleNamespace(id="discord-message-1")),
    )
    user = SimpleNamespace(
        id=1001,
        create_dm=AsyncMock(return_value=dm_channel),
        send=AsyncMock(return_value=SimpleNamespace(id="discord-message-1")),
    )
    bot = SimpleNamespace(
        get_user=lambda _user_id: user,
        fetch_user=AsyncMock(return_value=user),
        get_channel=lambda _channel_id: None,
        fetch_channel=AsyncMock(),
    )

    result = await deliver_notification(_command(envelope_id=envelope_id), bot=bot)

    expected_nonce = _expected_nonce(envelope_id)
    assert envelope_nonce(envelope_id) == expected_nonce
    assert len(expected_nonce) == 25
    assert dm_channel.send.await_count + user.send.await_count == 1
    send_mock = dm_channel.send if dm_channel.send.await_count else user.send
    kwargs = send_mock.await_args.kwargs
    assert kwargs["nonce"] == expected_nonce
    assert kwargs["enforce_nonce"] is True
    assert str(result.envelope_id) == str(envelope_id)
    assert result.discord_message_id == "discord-message-1"
    assert result.delivered_at <= datetime.now(UTC)
