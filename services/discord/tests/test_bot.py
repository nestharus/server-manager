from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from app.core.bot import HumilityBot
    from app.core.settings import Settings


@pytest.fixture
def settings() -> Settings:
    from app.core.settings import Settings

    return Settings(
        discord_bot_token="test-token",
        discord_guild_id=1,
        api_base_url="http://stub",
    )


@pytest.fixture
def bot(settings: Settings) -> HumilityBot:
    from app.core.bot import HumilityBot

    return HumilityBot(settings)


def test_humility_bot_is_importable_from_app_core_bot() -> None:
    module = importlib.import_module("app.core.bot")

    assert hasattr(module, "HumilityBot")


def test_humility_bot_construction_with_settings_succeeds_without_network(bot: HumilityBot) -> None:
    assert bot is not None
    assert bot.user is None


def test_humility_bot_stores_passed_settings_instance(bot: HumilityBot, settings: Settings) -> None:
    assert bot.settings is settings


def test_humility_bot_enables_member_intent(bot: HumilityBot) -> None:
    assert bot.intents.members is True


def test_humility_bot_enables_message_content_intent(bot: HumilityBot) -> None:
    assert bot.intents.message_content is True


def test_humility_bot_disables_presence_intent(bot: HumilityBot) -> None:
    assert bot.intents.presences is False


def test_humility_bot_is_a_commands_bot_instance(bot: HumilityBot) -> None:
    from discord.ext import commands

    assert isinstance(bot, commands.Bot)


def test_humility_bot_has_command_tree(bot: HumilityBot) -> None:
    assert hasattr(bot, "tree")
    assert bot.tree is not None
