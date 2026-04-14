import discord
from discord.ext import commands

from app.core.settings import Settings


class HumilityBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = False

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings: Settings = settings
