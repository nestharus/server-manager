"""Contract-level tests for the Discord test harness (WU-009B).

Asserts that the `DiscordTestHarnessRead` contract and the three required
fixtures (`bot`, `interaction_factory`, `api_client_stub`) are present and
behave per the Phase 0 harness contract.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.contracts.testing import DISCORD_TEST_HARNESS, DiscordTestHarnessRead
from app.core.bot import HumilityBot


def test_discord_test_harness_contract_field_shape() -> None:
    assert isinstance(DISCORD_TEST_HARNESS, DiscordTestHarnessRead)
    assert DISCORD_TEST_HARNESS.bot_fixture_name == "bot"
    assert DISCORD_TEST_HARNESS.interaction_factory_fixture_name == "interaction_factory"
    assert DISCORD_TEST_HARNESS.api_client_stub_fixture_name == "api_client_stub"


def test_bot_fixture_constructs_without_network(bot: HumilityBot) -> None:
    assert isinstance(bot, HumilityBot)
    assert bot.tree is not None
    assert bot.user is None


def test_interaction_factory_builds_interaction(
    interaction_factory: Callable[..., Any],
) -> None:
    interaction = interaction_factory(user_id=123, guild_id=456)

    assert interaction.user.id == 123
    assert interaction.guild.id == 456
    assert interaction.response is not None


@pytest.mark.asyncio()
async def test_api_client_stub_intercepts_http_calls(
    api_client_stub: httpx.MockTransport,
) -> None:
    async with httpx.AsyncClient(
        transport=api_client_stub,
        base_url="http://stub",
    ) as client:
        response = await client.get("/probe")

    assert response is not None
    recorded = getattr(api_client_stub, "requests", None)
    assert recorded is not None, (
        "api_client_stub fixture must expose a `requests` recorder per harness contract"
    )
    assert any(str(req.url).endswith("/probe") for req in recorded)


def test_command_registry_boots_without_network(bot: HumilityBot) -> None:
    commands = bot.tree.get_commands()

    assert isinstance(commands, list)
