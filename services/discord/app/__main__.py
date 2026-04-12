"""Discord daemon entry point.

Run with: cd services/discord && uv run python -m app
"""

from __future__ import annotations

import logging
import signal
import sys

from app.core.bot import HumilityBot
from app.core.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    settings = get_settings()
    bot = HumilityBot(settings)

    def shutdown(*_: object) -> None:
        logging.getLogger("server-manager.discord").info("Shutdown signal received")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    bot.run(settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    main()
