from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import discord
from discord.ext import commands

from app.commands import InteractionRegistry
from app.contracts.interactions import (
    InteractionEnvelope,
    InteractionHandler,
    InteractionResult,
)
from app.core.context import get_current_audit_context
from app.core.settings import Settings


class HumilityBot(commands.Bot):
    def __init__(self, settings: Settings, api_client: Any | None = None) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = False

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings: Settings = settings
        self.api_client = api_client
        self.registry = InteractionRegistry()

    def register_interaction_handler(
        self,
        command_name: str,
        handler: InteractionHandler,
    ) -> InteractionHandler:
        return self.registry.register(command_name, handler)

    async def dispatch_interaction(self, raw_interaction: Any) -> InteractionResult:
        envelope = InteractionEnvelope(
            interaction_id=str(raw_interaction.id),
            correlation_id=_interaction_correlation_id(),
            causation_id=_interaction_causation_id(),
            actor_kind="discord_user",
            actor_id=str(raw_interaction.user.id),
            guild_id=None
            if getattr(raw_interaction, "guild", None) is None
            else str(raw_interaction.guild.id),
            command_name=_interaction_command_name(raw_interaction),
            arguments=_interaction_arguments(raw_interaction),
        )
        result = await self.registry.dispatch(envelope)
        if result.response_text is not None and hasattr(raw_interaction.response, "send_message"):
            await raw_interaction.response.send_message(
                result.response_text,
                ephemeral=result.ephemeral,
            )
        return result


def _interaction_command_name(raw_interaction: Any) -> str:
    data = getattr(raw_interaction, "data", None) or {}
    return str(data.get("name", ""))


def _interaction_arguments(raw_interaction: Any) -> dict[str, Any]:
    data = getattr(raw_interaction, "data", None) or {}
    options = data.get("options") or []
    arguments: dict[str, Any] = {}
    for option in options:
        name = option.get("name")
        if name is None:
            continue
        arguments[str(name)] = option.get("value")
    return arguments


def _interaction_correlation_id() -> UUID:
    ctx = get_current_audit_context()
    if ctx is not None:
        return ctx.correlation_id
    return uuid4()


def _interaction_causation_id() -> UUID | None:
    ctx = get_current_audit_context()
    if ctx is not None:
        return ctx.causation_id
    return None
