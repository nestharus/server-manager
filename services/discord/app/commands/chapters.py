from __future__ import annotations

from app.handlers.chapters import provision_chapter_handler


PROVISION_CHAPTER_COMMAND = "provision_chapter"


def register_chapter_commands(bot):
    async def _handler(envelope):
        guild = None
        if envelope.guild_id is not None and hasattr(bot, "get_guild"):
            guild = bot.get_guild(int(envelope.guild_id))
        return await provision_chapter_handler(
            envelope,
            api_client=bot.api_client,
            guild=guild,
        )

    bot.register_interaction_handler(PROVISION_CHAPTER_COMMAND, _handler)


__all__ = ["PROVISION_CHAPTER_COMMAND", "register_chapter_commands"]
