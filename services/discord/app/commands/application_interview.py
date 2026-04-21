from __future__ import annotations

from app.handlers.application_interview import handle_application_interview


APPLICATION_INTERVIEW_COMMAND = "application_interview"


def register_application_interview_commands(bot) -> None:
    async def _resolve_guild(envelope):
        if envelope.guild_id is None or not hasattr(bot, "get_guild"):
            return None
        guild = bot.get_guild(int(envelope.guild_id))
        if guild is not None:
            return guild
        if hasattr(bot, "fetch_guild"):
            return await bot.fetch_guild(int(envelope.guild_id))
        return None

    async def _interview(envelope):
        return await handle_application_interview(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    bot.register_interaction_handler(APPLICATION_INTERVIEW_COMMAND, _interview)


__all__ = ["APPLICATION_INTERVIEW_COMMAND", "register_application_interview_commands"]
