from __future__ import annotations

from app.handlers.application_waitlist import (
    handle_application_reactivate,
    handle_application_waitlist,
)


APPLICATION_WAITLIST_COMMAND = "application_waitlist"
APPLICATION_REACTIVATE_COMMAND = "application_reactivate"


def register_application_waitlist_commands(bot) -> None:
    async def _resolve_guild(envelope):
        if envelope.guild_id is None or not hasattr(bot, "get_guild"):
            return None
        guild = bot.get_guild(int(envelope.guild_id))
        if guild is not None:
            return guild
        if hasattr(bot, "fetch_guild"):
            return await bot.fetch_guild(int(envelope.guild_id))
        return None

    async def _waitlist(envelope):
        return await handle_application_waitlist(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    async def _reactivate(envelope):
        return await handle_application_reactivate(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    bot.register_interaction_handler(APPLICATION_WAITLIST_COMMAND, _waitlist)
    bot.register_interaction_handler(APPLICATION_REACTIVATE_COMMAND, _reactivate)


__all__ = [
    "APPLICATION_REACTIVATE_COMMAND",
    "APPLICATION_WAITLIST_COMMAND",
    "register_application_waitlist_commands",
]
