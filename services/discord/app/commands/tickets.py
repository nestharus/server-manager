from __future__ import annotations

from app.handlers.tickets import handle_ticket_open, handle_ticket_transition


TICKET_OPEN_COMMAND = "ticket_open"
TICKET_TRANSITION_COMMAND = "ticket_transition"


def register_ticket_commands(bot):
    async def _open_handler(envelope):
        guild = None
        if envelope.guild_id is not None and hasattr(bot, "get_guild"):
            guild = bot.get_guild(int(envelope.guild_id))
        return await handle_ticket_open(
            envelope,
            api_client=bot.api_client,
            guild=guild,
        )

    async def _transition_handler(envelope):
        guild = None
        if envelope.guild_id is not None and hasattr(bot, "get_guild"):
            guild = bot.get_guild(int(envelope.guild_id))
        return await handle_ticket_transition(
            envelope,
            api_client=bot.api_client,
            guild=guild,
        )

    bot.register_interaction_handler(TICKET_OPEN_COMMAND, _open_handler)
    bot.register_interaction_handler(TICKET_TRANSITION_COMMAND, _transition_handler)


__all__ = [
    "TICKET_OPEN_COMMAND",
    "TICKET_TRANSITION_COMMAND",
    "register_ticket_commands",
]
