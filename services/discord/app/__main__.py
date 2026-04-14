"""Discord daemon package entry point."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

import discord
from pydantic import ValidationError

from app.core.bot import HumilityBot
from app.core.settings import Settings


logger = logging.getLogger(__name__)


async def main() -> int:
    """Run the Discord daemon."""
    discord.utils.setup_logging()

    try:
        settings = Settings()
    except ValidationError:
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
