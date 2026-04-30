from __future__ import annotations

import base64
import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest


def _load_notifications_handler() -> Any:
    try:
        return importlib.import_module("app.handlers.notifications")
    except ModuleNotFoundError as error:
        pytest.fail(f"missing Discord notification handler module: {error}")


def _expected_nonce(envelope_id: UUID) -> str:
    return base64.b32encode(envelope_id.bytes).decode("ascii").rstrip("=")[:25]


def _command(
    *,
    envelope_id: UUID,
    channel: str = "dm",
    recipient_discord_id: str | None = "1001",
    destination_channel_id: str | None = None,
    rendered_embed_json: dict[str, Any] | None = None,
) -> Any:
    envelope = SimpleNamespace(
        id=envelope_id,
        rendered_title="",
        rendered_body="Body",
        recipient_discord_id=recipient_discord_id,
        recipient_display="1001",
        channel=channel,
        destination_channel_id=destination_channel_id,
        actionable=False,
        rendered_embed_json=rendered_embed_json,
    )
    return SimpleNamespace(envelope=envelope)


def _embed_json() -> dict[str, Any]:
    return {
        "title": "New application submission - Global",
        "description": "I want to join scheduled guild activities.",
        "url": "https://web.test.humility.local/applications/app-1",
        "color": 3447003,
        "fields": [
            {"name": "Application ID", "value": "app-1", "inline": False},
            {"name": "Scope", "value": "Global", "inline": True},
        ],
    }


def _assert_tg3(*, named_risk: str) -> None:
    group = "TG-3"
    level = "component"
    source = ".tmp/init-134/phase6/step6a-contract.md#TG-3"
    assert group.startswith("TG-")
    assert named_risk
    assert level == "component"
    assert source


def _assert_embed_matches(embed: Any) -> None:
    assert embed is not None
    assert getattr(embed, "title", None) == "New application submission - Global"
    assert getattr(embed, "description", None) == "I want to join scheduled guild activities."
    assert getattr(embed, "url", None) == "https://web.test.humility.local/applications/app-1"
    color = getattr(embed, "color", None)
    assert getattr(color, "value", color) == 3447003
    fields = list(getattr(embed, "fields", []))
    assert len(fields) == 2
    assert getattr(fields[0], "name", None) == "Application ID"
    assert getattr(fields[0], "value", None) == "app-1"
    assert getattr(fields[0], "inline", None) is False
    assert getattr(fields[1], "inline", None) is True


@pytest.mark.asyncio
async def test_dm_delivery_with_embed_calls_send_with_embed_param() -> None:
    """Risk annotation: group=TG-3; named_risk=dm_embed_delivery_drops_embed;
    level=component; source=.tmp/init-134/phase6/step6a-contract.md#TG-3.
    """
    _assert_tg3(named_risk="dm_embed_delivery_drops_embed")
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification")
    envelope_id = UUID("12345678-1234-5678-1234-567812345678")
    dm_channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id="m-1")))
    user = SimpleNamespace(id=1001, dm_channel=dm_channel, create_dm=AsyncMock())
    bot = SimpleNamespace(fetch_user=AsyncMock(return_value=user))

    await deliver_notification(
        _command(envelope_id=envelope_id, rendered_embed_json=_embed_json()),
        bot=bot,
    )

    kwargs = dm_channel.send.await_args.kwargs
    assert kwargs["content"] == "Body"
    assert kwargs["nonce"] == _expected_nonce(envelope_id)
    assert kwargs["enforce_nonce"] is True
    _assert_embed_matches(kwargs["embed"])


@pytest.mark.asyncio
async def test_channel_delivery_with_embed_calls_send_with_embed_param() -> None:
    """Risk annotation: group=TG-3; named_risk=channel_embed_delivery_drops_embed;
    level=component; source=.tmp/init-134/phase6/step6a-contract.md#TG-3.
    """
    _assert_tg3(named_risk="channel_embed_delivery_drops_embed")
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification")
    envelope_id = UUID("12345678-1234-5678-1234-567812345679")
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id="m-2")))
    bot = SimpleNamespace(fetch_channel=AsyncMock(return_value=channel))

    await deliver_notification(
        _command(
            envelope_id=envelope_id,
            channel="designated_channel",
            destination_channel_id="222222222222222222",
            rendered_embed_json=_embed_json(),
        ),
        bot=bot,
    )

    kwargs = channel.send.await_args.kwargs
    assert kwargs["content"] == "Body"
    assert kwargs["nonce"] == _expected_nonce(envelope_id)
    assert kwargs["enforce_nonce"] is True
    _assert_embed_matches(kwargs["embed"])


@pytest.mark.asyncio
async def test_text_only_delivery_unchanged_for_dms() -> None:
    """Risk annotation: group=TG-3; named_risk=text_only_dm_delivery_regression;
    level=component; source=.tmp/init-134/phase6/step6a-contract.md#TG-3.
    """
    _assert_tg3(named_risk="text_only_dm_delivery_regression")
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification")
    dm_channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id="m-3")))
    user = SimpleNamespace(id=1001, dm_channel=dm_channel, create_dm=AsyncMock())
    bot = SimpleNamespace(fetch_user=AsyncMock(return_value=user))

    await deliver_notification(
        _command(
            envelope_id=UUID("12345678-1234-5678-1234-567812345680"),
            rendered_embed_json=None,
        ),
        bot=bot,
    )

    kwargs = dm_channel.send.await_args.kwargs
    assert kwargs["content"] == "Body"
    assert "embed" not in kwargs


@pytest.mark.asyncio
async def test_text_only_delivery_unchanged_for_channels() -> None:
    """Risk annotation: group=TG-3; named_risk=text_only_channel_delivery_regression;
    level=component; source=.tmp/init-134/phase6/step6a-contract.md#TG-3.
    """
    _assert_tg3(named_risk="text_only_channel_delivery_regression")
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification")
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id="m-4")))
    bot = SimpleNamespace(fetch_channel=AsyncMock(return_value=channel))

    await deliver_notification(
        _command(
            envelope_id=UUID("12345678-1234-5678-1234-567812345681"),
            channel="designated_channel",
            destination_channel_id="222222222222222222",
            rendered_embed_json=None,
        ),
        bot=bot,
    )

    kwargs = channel.send.await_args.kwargs
    assert kwargs["content"] == "Body"
    assert "embed" not in kwargs


@pytest.mark.asyncio
async def test_nonce_idempotency_preserved_with_embed() -> None:
    """Risk annotation: group=TG-3; named_risk=embed_delivery_nonce_regression;
    level=component; source=.tmp/init-134/phase6/step6a-contract.md#TG-3.
    """
    _assert_tg3(named_risk="embed_delivery_nonce_regression")
    handler_module = _load_notifications_handler()
    deliver_notification = getattr(handler_module, "deliver_notification")
    envelope_nonce = getattr(handler_module, "envelope_nonce")
    envelope_id = UUID("12345678-1234-5678-1234-567812345682")
    dm_channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id="m-5")))
    user = SimpleNamespace(id=1001, dm_channel=dm_channel, create_dm=AsyncMock())
    bot = SimpleNamespace(fetch_user=AsyncMock(return_value=user))

    await deliver_notification(
        _command(envelope_id=envelope_id, rendered_embed_json=_embed_json()),
        bot=bot,
    )

    assert envelope_nonce(envelope_id) == _expected_nonce(envelope_id)
    kwargs = dm_channel.send.await_args.kwargs
    assert kwargs["nonce"] == _expected_nonce(envelope_id)
    assert kwargs["enforce_nonce"] is True
    assert "embed" in kwargs
