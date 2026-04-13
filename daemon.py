"""Discord daemon entry point for the Humility guild."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from daemon.config import DaemonConfig, load_config
from daemon.db import close_database, open_database


ENV_PATH = Path(__file__).with_name(".env")
BASE_PATH = Path(__file__).resolve().parent

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class RuntimeConfig:
    token: str
    guild_id: int
    base_path: Path
    database_path: Path


def get_runtime_config() -> RuntimeConfig:
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id_raw = os.getenv("DISCORD_GUILD_ID")
    database_path_raw = os.getenv("DATABASE_PATH")

    if not token:
        raise RuntimeError(f"DISCORD_BOT_TOKEN is missing in {ENV_PATH}")
    if not guild_id_raw:
        raise RuntimeError(f"DISCORD_GUILD_ID is missing in {ENV_PATH}")

    try:
        guild_id = int(guild_id_raw)
    except ValueError as exc:
        raise RuntimeError("DISCORD_GUILD_ID must be an integer") from exc

    database_path = Path(database_path_raw) if database_path_raw else BASE_PATH / "discord.db"
    return RuntimeConfig(
        token=token,
        guild_id=guild_id,
        base_path=BASE_PATH,
        database_path=database_path,
    )


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = False
    return intents


class HumilityDaemonBot(commands.Bot):
    def __init__(
        self,
        *,
        guild_id: int,
        config: DaemonConfig,
        conn: sqlite3.Connection,
        intents: discord.Intents,
        base_path: Path | None = None,
    ) -> None:
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.guild_id = guild_id
        self.config = config
        self.conn = conn
        self.base_path = base_path

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.guild_id)

        @app_commands.guilds(guild)
        @self.tree.command(name="ping", description="Check whether the daemon is alive")
        async def ping(interaction: discord.Interaction) -> None:
            await interaction.response.send_message("daemon is alive", ephemeral=True)

        await self.tree.sync(guild=guild)


async def main() -> None:
    runtime = get_runtime_config()
    config = load_config(runtime.base_path)
    conn = open_database(runtime.database_path)

    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        bot = HumilityDaemonBot(
            guild_id=runtime.guild_id,
            config=config,
            conn=conn,
            intents=build_intents(),
            base_path=runtime.base_path,
        )
        async with bot:
            await bot.start(runtime.token)
    finally:
        close_database(conn)


if __name__ == "__main__":
    asyncio.run(main())
