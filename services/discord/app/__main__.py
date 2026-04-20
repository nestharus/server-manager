"""Discord daemon package entry point."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

import discord

from app.core.bot import HumilityBot
from app.core.settings import (
    Settings,
    SettingsConstructionError,
    load_settings as _core_load_settings,
)


logger = logging.getLogger(__name__)

_CORE_SETTINGS_TYPE = Settings


def load_settings() -> Settings:
    if Settings is _CORE_SETTINGS_TYPE:
        return _core_load_settings()
    return Settings()


async def main() -> int:
    """Run the Discord daemon."""
    discord.utils.setup_logging()

    try:
        settings = load_settings()
    except SettingsConstructionError as exc:
        if exc.missing_env_vars:
            logger.exception(
                "Failed to construct Discord settings. Missing required env vars: %s",
                ", ".join(exc.missing_env_vars),
            )
        else:
            logger.exception("Failed to construct Discord settings.")
        return 1

    bot = HumilityBot(settings)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(bot.close()))

    try:
        try:
            await bot.start(settings.discord_bot_token)
        finally:
            await bot.close()
    except KeyboardInterrupt:
        return 0
    except (
        discord.LoginFailure,
        discord.GatewayNotFound,
        discord.PrivilegedIntentsRequired,
    ):
        logger.exception("Discord daemon failed to start.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
