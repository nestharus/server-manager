from __future__ import annotations

from app.handlers.application_review import (
    handle_application_approve,
    handle_application_claim,
    handle_application_deny,
)


APPLICATION_CLAIM_COMMAND = "application_claim"
APPLICATION_APPROVE_COMMAND = "application_approve"
APPLICATION_DENY_COMMAND = "application_deny"


def register_application_review_commands(bot) -> None:
    async def _resolve_guild(envelope):
        if envelope.guild_id is None or not hasattr(bot, "get_guild"):
            return None
        return bot.get_guild(int(envelope.guild_id))

    async def _claim(envelope):
        return await handle_application_claim(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    async def _approve(envelope):
        return await handle_application_approve(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    async def _deny(envelope):
        return await handle_application_deny(
            envelope,
            api_client=bot.api_client,
            guild=await _resolve_guild(envelope),
        )

    bot.register_interaction_handler(APPLICATION_CLAIM_COMMAND, _claim)
    bot.register_interaction_handler(APPLICATION_APPROVE_COMMAND, _approve)
    bot.register_interaction_handler(APPLICATION_DENY_COMMAND, _deny)


__all__ = [
    "APPLICATION_APPROVE_COMMAND",
    "APPLICATION_CLAIM_COMMAND",
    "APPLICATION_DENY_COMMAND",
    "register_application_review_commands",
]
