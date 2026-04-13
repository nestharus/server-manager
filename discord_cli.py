#!/usr/bin/env python3
"""discord_cli.py — thin CLI around discord.py for inspecting and managing a guild.

Every subcommand opens a gateway session, runs once, prints JSON to stdout,
and exits. Token and guild ID come from .env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import discord
from dotenv import load_dotenv

ENV_PATH = Path("/home/nes/discord/.env")

load_dotenv(ENV_PATH)


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, default=json_default))


def get_config() -> tuple[str, int]:
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id_raw = os.getenv("DISCORD_GUILD_ID")

    if not token:
        raise RuntimeError(f"DISCORD_BOT_TOKEN is missing in {ENV_PATH}")
    if not guild_id_raw:
        raise RuntimeError(f"DISCORD_GUILD_ID is missing in {ENV_PATH}")

    try:
        guild_id = int(guild_id_raw)
    except ValueError as exc:
        raise RuntimeError("DISCORD_GUILD_ID must be an integer") from exc

    return token, guild_id


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return intents


async def run_gateway_command(
    handler: Callable[[discord.Client, discord.Guild], Awaitable[Any]],
) -> Any:
    token, guild_id = get_config()
    client = discord.Client(intents=build_intents())
    result: dict[str, Any] = {}

    @client.event
    async def on_ready() -> None:
        try:
            guild = client.get_guild(guild_id)
            if guild is None:
                raise RuntimeError(f"Guild {guild_id} is not available to the bot")
            result["payload"] = await handler(client, guild)
        except Exception as exc:  # pragma: no cover - surfaced after disconnect
            result["error"] = exc
        finally:
            await client.close()

    await client.start(token)

    if "error" in result:
        raise result["error"]

    return result["payload"]


async def fetch_overview(client: discord.Client, guild: discord.Guild) -> dict[str, Any]:
    owner = guild.owner
    if owner is None:
        owner = await guild.fetch_member(guild.owner_id)

    return {
        "name": guild.name,
        "id": guild.id,
        "owner": {
            "id": owner.id,
            "name": str(owner),
        },
        "member_count": guild.member_count,
        "channel_count": len(guild.channels),
        "role_count": len(guild.roles),
        "boost_level": guild.premium_tier,
        "created_date": guild.created_at,
    }


async def cmd_overview(_: argparse.Namespace) -> int:
    payload = await run_gateway_command(fetch_overview)
    print_json(payload)
    return 0


def cmd_not_yet_implemented(_: argparse.Namespace) -> int:
    print_json("not yet implemented")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    overview_parser = subparsers.add_parser("overview", help="Show guild overview")
    overview_parser.set_defaults(func=cmd_overview)

    for name, help_text in (
        ("bots", "List bot members"),
        ("channels", "List all channels"),
        ("find-channel", "Find a channel by name"),
        ("read", "Read messages from a channel"),
        ("integrations", "List guild integrations"),
    ):
        stub_parser = subparsers.add_parser(name, help=help_text)
        stub_parser.set_defaults(func=cmd_not_yet_implemented)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if asyncio.iscoroutinefunction(args.func):
            return asyncio.run(args.func(args))
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except discord.DiscordException as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
