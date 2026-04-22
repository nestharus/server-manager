from __future__ import annotations

from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.handlers.permissions import handle_reconcile_permissions


RECONCILE_PERMISSIONS_COMMAND = "reconcile_permissions"


def register_permission_commands(bot: object) -> None:
    async def _handler(envelope: InteractionEnvelope) -> InteractionResult:
        guild = None
        if envelope.guild_id is not None and hasattr(bot, "get_guild"):
            guild = bot.get_guild(int(envelope.guild_id))  # type: ignore[attr-defined]
        return await handle_reconcile_permissions(
            envelope,
            permission_client=bot.permission_client,  # type: ignore[attr-defined]
            guild=guild,
        )

    bot.register_interaction_handler(  # type: ignore[attr-defined]
        RECONCILE_PERMISSIONS_COMMAND, _handler,
    )


__all__ = [
    "RECONCILE_PERMISSIONS_COMMAND",
    "register_permission_commands",
]
