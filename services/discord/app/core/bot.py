"""Discord bot client setup.

Creates the discord.py Client with intents and command tree.
The bot is the gateway adapter — it translates Discord interactions
into API calls or direct DB writes.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from app.core.settings import Settings

log = logging.getLogger("server-manager.discord")


def make_intents() -> discord.Intents:
    i = discord.Intents.default()
    i.members = True
    i.message_content = True
    i.guilds = True
    return i


class HumilityBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        super().__init__(intents=make_intents())
        self.tree = app_commands.CommandTree(self)
        self.settings = settings
        self._guild_obj = discord.Object(id=settings.active_guild_id)

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=self._guild_obj)
        await self.tree.sync(guild=self._guild_obj)
        log.info("Synced slash commands to guild %d", self.settings.active_guild_id)

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Logged in as %s (id %d)", self.user, self.user.id)
        guild = self.get_guild(self.settings.active_guild_id)
        if guild is None:
            log.error("Bot is not in guild %d", self.settings.active_guild_id)
            await self.close()
            return
        log.info("Connected to guild: %s (%d members)", guild.name, guild.member_count)
