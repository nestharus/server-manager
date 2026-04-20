from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from unittest.mock import AsyncMock

from app.core.bot import HumilityBot
from app.core.settings import Settings


@pytest.fixture
def bot() -> HumilityBot:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=900000000000000001,
        api_base_url="http://stub.api",
    )
    return HumilityBot(settings)


@pytest.fixture
def interaction_factory() -> Callable[..., Any]:
    def factory(*, user_id: int = 1, guild_id: int = 900000000000000001) -> Any:
        return SimpleNamespace(
            user=SimpleNamespace(id=user_id),
            guild=SimpleNamespace(id=guild_id),
            response=SimpleNamespace(
                send_message=AsyncMock(),
                defer=AsyncMock(),
                edit_message=AsyncMock(),
            ),
        )

    return factory


@pytest.fixture
def api_client_stub() -> httpx.MockTransport:
    response_specs: list[dict[str, Any]] = []
    requests: list[httpx.Request] = []

    def queue_response(
        *,
        status_code: int = 200,
        json: Any | None = None,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"status_code": status_code}
        if headers is not None:
            kwargs["headers"] = headers
        if json is not None:
            kwargs["json"] = json
        if text is not None:
            kwargs["text"] = text
        response_specs.append(kwargs)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if response_specs:
            return httpx.Response(request=request, **response_specs.pop(0))
        return httpx.Response(status_code=200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    transport.requests = requests  # type: ignore[attr-defined]
    transport.queue_response = queue_response  # type: ignore[attr-defined]
    return transport
