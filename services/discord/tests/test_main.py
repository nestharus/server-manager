from __future__ import annotations

import importlib
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
import pytest


EXPECTED_MODULE_DOCSTRING = "Discord daemon package entry point."


def _import_main_module():
    return importlib.import_module("app.__main__")


def _make_settings(token: str = "test-token") -> SimpleNamespace:
    return SimpleNamespace(
        discord_bot_token=token,
        discord_guild_id=1,
        api_base_url="http://stub",
    )


def _make_bot(*, start_side_effect: BaseException | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        start=AsyncMock(side_effect=start_side_effect),
        close=AsyncMock(),
    )


def test_main_is_importable_from_app_dunder_main() -> None:
    module = _import_main_module()

    assert hasattr(module, "main")


def test_main_is_an_async_function() -> None:
    module = _import_main_module()

    assert inspect.iscoroutinefunction(module.main)


def test_main_module_has_expected_docstring() -> None:
    module = _import_main_module()

    assert module.__doc__ == EXPECTED_MODULE_DOCSTRING


def test_build_bot_with_registry_registers_interaction_commands() -> None:
    module = _import_main_module()
    settings = _make_settings()
    registered: list[str] = []
    bot = SimpleNamespace(
        register_interaction_handler=lambda name, handler: registered.append(name),
    )

    with patch.object(module, "HumilityBot", return_value=bot, create=True):
        result = module.build_bot_with_registry(settings=settings, api_client=object())

    assert result is bot
    assert registered == [
        "application_claim",
        "application_approve",
        "application_deny",
        "application_submit",
        "provision_chapter",
        "ticket_open",
        "ticket_transition",
    ]


@pytest.mark.asyncio
async def test_main_returns_one_when_settings_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _import_main_module()

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)

    assert await module.main() == 1


@pytest.mark.asyncio
async def test_main_closes_bot_in_finally_when_start_raises_gateway_not_found() -> None:
    module = _import_main_module()
    settings = _make_settings()
    bot = _make_bot(start_side_effect=discord.GatewayNotFound())

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    with (
        patch.object(module, "Settings", return_value=settings, create=True),
        patch.object(module, "HumilityBot", return_value=bot, create=True),
        patch.object(module, "check_api_reachability", side_effect=_noop_reachability),
    ):
        assert await module.main() == 1

    bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_starts_bot_with_token_from_settings() -> None:
    module = _import_main_module()
    settings = _make_settings(token="discord-token-from-settings")
    bot = _make_bot()

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    with (
        patch.object(module, "Settings", return_value=settings, create=True),
        patch.object(module, "HumilityBot", return_value=bot, create=True),
        patch.object(module, "check_api_reachability", side_effect=_noop_reachability),
    ):
        assert await module.main() == 0

    bot.start.assert_awaited_once_with("discord-token-from-settings")
    bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_returns_zero_on_keyboard_interrupt_during_start() -> None:
    module = _import_main_module()
    settings = _make_settings()
    bot = _make_bot(start_side_effect=KeyboardInterrupt())

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    with (
        patch.object(module, "Settings", return_value=settings, create=True),
        patch.object(module, "HumilityBot", return_value=bot, create=True),
        patch.object(module, "check_api_reachability", side_effect=_noop_reachability),
    ):
        assert await module.main() == 0

    bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_returns_one_on_login_failure() -> None:
    module = _import_main_module()
    settings = _make_settings()
    bot = _make_bot(start_side_effect=discord.LoginFailure("invalid token"))

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    with (
        patch.object(module, "Settings", return_value=settings, create=True),
        patch.object(module, "HumilityBot", return_value=bot, create=True),
        patch.object(module, "check_api_reachability", side_effect=_noop_reachability),
    ):
        assert await module.main() == 1

    bot.close.assert_awaited_once()
