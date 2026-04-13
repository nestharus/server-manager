#!/usr/bin/env python3
"""One-shot Discord inspection CLI for the configured guild."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import discord
from dotenv import load_dotenv

ENV_PATH = Path(__file__).with_name(".env")
MAX_READ_LIMIT = 200
DEFAULT_READ_LIMIT = 50
GATEWAY_TIMEOUT_SECONDS = 30

load_dotenv(ENV_PATH)


class CLIError(RuntimeError):
    def __init__(
        self,
        error_type: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}
        self.exit_code = exit_code


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
    intents.guilds = True
    intents.members = True
    intents.message_content = True
    return intents


def success_payload(command: str, guild_id: int, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "guild_id": guild_id,
        "data": data,
    }


def error_payload(
    command: str | None,
    guild_id: int | None,
    error_type: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "guild_id": guild_id,
        "error": {
            "type": error_type,
            "message": message,
            "details": details or {},
        },
    }


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def safe_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def serialize_member_identity(member: Any) -> dict[str, Any]:
    return {
        "id": member.id,
        "name": str(member),
        "display_name": getattr(member, "display_name", None),
    }


def serialize_bot_member(member: Any) -> dict[str, Any]:
    roles = list(getattr(member, "roles", []))
    return {
        "id": member.id,
        "username": getattr(member, "name", None),
        "display_name": getattr(member, "display_name", None),
        "nick": getattr(member, "nick", None),
        "joined_at": iso_or_none(getattr(member, "joined_at", None)),
        "role_ids": [role.id for role in roles],
        "role_names": [role.name for role in roles],
    }


def serialize_author(member: Any) -> dict[str, Any]:
    return {
        "id": member.id,
        "name": str(member),
        "display_name": getattr(member, "display_name", None),
        "bot": bool(getattr(member, "bot", False)),
    }


def serialize_channel(channel: Any, *, kind: str = "channel") -> dict[str, Any]:
    category = getattr(channel, "category", None)
    parent = getattr(channel, "parent", None)

    payload = {
        "id": channel.id,
        "name": channel.name,
        "type": str(channel.type),
        "kind": kind,
        "category_id": getattr(category, "id", None),
        "category_name": getattr(category, "name", None),
        "parent_id": getattr(parent, "id", None),
        "parent_name": getattr(parent, "name", None),
    }

    if hasattr(channel, "position"):
        payload["position"] = getattr(channel, "position")
    if hasattr(channel, "nsfw"):
        payload["nsfw"] = getattr(channel, "nsfw")
    if getattr(channel, "topic", None) is not None:
        payload["topic"] = getattr(channel, "topic")

    return payload


def serialize_attachment(attachment: Any) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "content_type": getattr(attachment, "content_type", None),
        "size": getattr(attachment, "size", None),
        "url": getattr(attachment, "url", None),
    }


def serialize_embed(embed: Any) -> dict[str, Any]:
    return {
        "title": getattr(embed, "title", None),
        "url": getattr(embed, "url", None),
        "type": safe_str(getattr(embed, "type", None)),
    }


def serialize_message(message: Any) -> dict[str, Any]:
    return {
        "id": message.id,
        "created_at": iso_or_none(getattr(message, "created_at", None)),
        "edited_at": iso_or_none(getattr(message, "edited_at", None)),
        "author": serialize_author(message.author),
        "content": getattr(message, "content", None),
        "attachments": [serialize_attachment(item) for item in getattr(message, "attachments", [])],
        "embeds": [serialize_embed(item) for item in getattr(message, "embeds", [])],
        "pinned": bool(getattr(message, "pinned", False)),
        "tts": bool(getattr(message, "tts", False)),
        "type": safe_str(getattr(message, "type", None)),
        "jump_url": getattr(message, "jump_url", None),
    }


def serialize_integration(integration: Any) -> dict[str, Any]:
    account = getattr(integration, "account", None)
    user = getattr(integration, "user", None)

    return {
        "id": integration.id,
        "name": integration.name,
        "type": safe_str(getattr(integration, "type", None)),
        "enabled": bool(getattr(integration, "enabled", False)),
        "account": {
            "id": getattr(account, "id", None),
            "name": getattr(account, "name", None),
        }
        if account is not None
        else None,
        "user": {
            "id": getattr(user, "id", None),
            "name": str(user),
        }
        if user is not None
        else None,
        "application_id": getattr(integration, "application_id", None),
    }


def serialize_role(role: Any) -> dict[str, Any]:
    return {
        "id": role.id,
        "name": role.name,
        "color": role.color.value,
        "hoist": role.hoist,
        "position": role.position,
        "permissions": role.permissions.value,
        "managed": role.managed,
        "mentionable": role.mentionable,
        "is_default": role.is_default(),
        "is_bot_managed": role.is_bot_managed(),
        "is_integration": role.is_integration(),
        "is_premium_subscriber": role.is_premium_subscriber(),
        "created_at": iso_or_none(getattr(role, "created_at", None)),
    }


def combined_channels(guild: discord.Guild) -> list[Any]:
    return [*list(getattr(guild, "channels", [])), *list(getattr(guild, "threads", []))]


def sort_channel_matches(channels: list[Any], query: str) -> list[Any]:
    lowered = query.casefold()

    def sort_key(channel: Any) -> tuple[int, int, str]:
        name = channel.name.casefold()
        exact_rank = 0 if name == lowered else 1
        position = getattr(channel, "position", 0)
        return (exact_rank, position, name)

    return sorted(channels, key=sort_key)


def resolve_channel(guild: discord.Guild, selector: str) -> Any:
    try:
        channel_id = int(selector)
    except ValueError:
        channel_id = None

    if channel_id is not None:
        direct = guild.get_channel(channel_id) or guild.get_thread(channel_id)
        if direct is not None:
            return direct

    candidates = combined_channels(guild)
    lowered = selector.casefold()

    exact = [channel for channel in candidates if channel.name.casefold() == lowered]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CLIError(
            "channel_ambiguous",
            f"Multiple channels matched '{selector}'",
            details={"selector": selector, "candidates": [serialize_channel(item, kind=channel_kind(item)) for item in sort_channel_matches(exact, selector)]},
        )

    partial = [channel for channel in candidates if lowered in channel.name.casefold()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise CLIError(
            "channel_ambiguous",
            f"Multiple channels matched '{selector}'",
            details={"selector": selector, "candidates": [serialize_channel(item, kind=channel_kind(item)) for item in sort_channel_matches(partial, selector)]},
        )

    raise CLIError(
        "channel_not_found",
        f"No channel matched '{selector}'",
        details={"selector": selector},
    )


def channel_kind(channel: Any) -> str:
    threads = getattr(getattr(channel, "guild", None), "threads", None)
    try:
        if threads is not None and channel in threads:
            return "thread"
    except TypeError:
        pass

    return "thread" if "thread" in str(getattr(channel, "type", "")) else "channel"


def is_history_capable_channel(channel: Any) -> bool:
    return isinstance(
        channel,
        (
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.Thread,
        ),
    )


async def run_gateway_command(
    handler: Callable[[discord.Client, discord.Guild], Awaitable[Any]],
) -> Any:
    token, guild_id = get_config()
    client = discord.Client(intents=build_intents())
    result: dict[str, Any] = {}
    has_run = False

    @client.event
    async def on_ready() -> None:
        nonlocal has_run
        if has_run:
            return
        has_run = True

        try:
            guild = client.get_guild(guild_id)
            if guild is None:
                raise CLIError("guild_not_found", f"Guild {guild_id} is not available to the bot")
            if getattr(guild, "unavailable", False):
                raise CLIError("guild_unavailable", f"Guild {guild_id} is unavailable")
            result["payload"] = await handler(client, guild)
        except Exception as exc:  # pragma: no cover - surfaced after disconnect
            result["error"] = exc
        finally:
            await client.close()

    try:
        await asyncio.wait_for(
            client.start(token, reconnect=False),
            timeout=GATEWAY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await client.close()
        raise CLIError(
            "timeout_error",
            f"Gateway connection timed out after {GATEWAY_TIMEOUT_SECONDS}s",
        )

    if "error" in result:
        raise result["error"]

    return result.get("payload")


async def fetch_overview(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    owner = guild.owner
    if owner is None:
        owner = await guild.fetch_member(guild.owner_id)

    return {
        "name": guild.name,
        "id": guild.id,
        "owner": serialize_member_identity(owner),
        "member_count": guild.member_count,
        "channel_count": len(getattr(guild, "channels", [])),
        "role_count": len(getattr(guild, "roles", [])),
        "boost_tier": getattr(guild, "premium_tier", None),
        "boost_count": getattr(guild, "premium_subscription_count", None),
        "created_at": iso_or_none(getattr(guild, "created_at", None)),
        "unavailable": bool(getattr(guild, "unavailable", False)),
    }


async def fetch_bots(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    members = list(getattr(guild, "members", []))
    if not members and getattr(guild, "member_count", 0):
        raise CLIError(
            "intent_error",
            "Guild member cache is empty; enable the members intent for this bot",
        )

    bots = [serialize_bot_member(member) for member in members if getattr(member, "bot", False)]
    return {
        "count": len(bots),
        "bots": bots,
    }


async def fetch_channels(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    return {
        "channels": [serialize_channel(channel, kind="channel") for channel in getattr(guild, "channels", [])],
        "threads": [serialize_channel(thread, kind="thread") for thread in getattr(guild, "threads", [])],
    }


async def fetch_find_channel(guild: discord.Guild, args: argparse.Namespace) -> dict[str, Any]:
    matches = [
        serialize_channel(channel, kind="thread" if "thread" in str(channel.type) else "channel")
        for channel in sort_channel_matches(
            [channel for channel in combined_channels(guild) if args.name.casefold() in channel.name.casefold()],
            args.name,
        )
    ]

    return {
        "query": args.name,
        "count": len(matches),
        "matches": matches,
    }


async def fetch_read(guild: discord.Guild, args: argparse.Namespace) -> dict[str, Any]:
    if args.limit <= 0:
        raise CLIError("usage_error", "--limit must be greater than zero", exit_code=1)

    limit = min(args.limit, MAX_READ_LIMIT)
    channel = resolve_channel(guild, args.channel)

    messages = [message async for message in channel.history(limit=limit)]
    messages.reverse()

    return {
        "channel": serialize_channel(channel, kind="thread" if "thread" in str(channel.type) else "channel"),
        "limit": limit,
        "message_count": len(messages),
        "messages": [serialize_message(message) for message in messages],
    }


async def fetch_bot_activity(guild: discord.Guild, args: argparse.Namespace) -> dict[str, Any]:
    if args.per_channel_limit <= 0:
        raise CLIError("usage_error", "--per-channel-limit must be greater than zero", exit_code=1)

    total_messages_seen = 0
    last_seen: datetime | None = None
    per_channel = []
    matched_messages = []

    for channel in combined_channels(guild):
        if not is_history_capable_channel(channel):
            continue

        try:
            matches = [
                message
                async for message in channel.history(limit=args.per_channel_limit)
                if message.author.id == args.bot_id
            ]
        except discord.Forbidden:
            continue

        if not matches:
            continue

        channel_last_seen = max(message.created_at for message in matches)
        if last_seen is None or channel_last_seen > last_seen:
            last_seen = channel_last_seen

        total_messages_seen += len(matches)
        matched_messages.extend(matches)

        serialized_channel = serialize_channel(channel, kind=channel_kind(channel))
        per_channel.append(
            {
                "channel_id": serialized_channel["id"],
                "channel_name": serialized_channel["name"],
                "count": len(matches),
                "last_seen": iso_or_none(channel_last_seen),
            }
        )

    per_channel.sort(key=lambda item: (item["count"], item["last_seen"]), reverse=True)

    matched_messages.sort(key=lambda message: message.created_at, reverse=True)

    return {
        "bot_id": args.bot_id,
        "total_messages_seen": total_messages_seen,
        "last_seen": iso_or_none(last_seen),
        "per_channel": per_channel,
        "samples": [serialize_message(message) for message in matched_messages[:10]],
    }


async def fetch_integrations(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    integrations = [serialize_integration(item) for item in await guild.integrations()]
    return {
        "count": len(integrations),
        "integrations": integrations,
    }


async def fetch_roles(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    roles = [serialize_role(role) for role in getattr(guild, "roles", [])]
    return {
        "count": len(roles),
        "roles": roles,
    }


def command_specs() -> dict[str, Callable[[discord.Guild, argparse.Namespace], Awaitable[dict[str, Any]]]]:
    return {
        "overview": fetch_overview,
        "bots": fetch_bots,
        "channels": fetch_channels,
        "find-channel": fetch_find_channel,
        "read": fetch_read,
        "bot-activity": fetch_bot_activity,
        "integrations": fetch_integrations,
        "roles": fetch_roles,
    }


async def run_command(args: argparse.Namespace) -> int:
    command = args.command
    handler = command_specs()[command]
    _, guild_id = get_config()

    async def gateway_handler(_: discord.Client, guild: discord.Guild) -> dict[str, Any]:
        return await handler(guild, args)

    data = await run_gateway_command(gateway_handler)
    print_json(success_payload(command, guild_id, data))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("overview", "Show guild overview"),
        ("bots", "List bot members"),
        ("channels", "List guild channels and threads"),
        ("integrations", "List guild integrations"),
        ("roles", "List guild roles"),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.set_defaults(func=run_command)

    find_channel_parser = subparsers.add_parser("find-channel", help="Find a channel by name")
    find_channel_parser.add_argument("name")
    find_channel_parser.set_defaults(func=run_command)

    read_parser = subparsers.add_parser("read", help="Read messages from a channel")
    read_parser.add_argument("channel")
    read_parser.add_argument("--limit", type=int, default=DEFAULT_READ_LIMIT)
    read_parser.set_defaults(func=run_command)

    bot_activity_parser = subparsers.add_parser("bot-activity", help="Scan channels for activity by a bot")
    bot_activity_parser.add_argument("bot_id", type=int)
    bot_activity_parser.add_argument("--per-channel-limit", type=int, default=100)
    bot_activity_parser.set_defaults(func=run_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)

    try:
        return asyncio.run(args.func(args))
    except CLIError as exc:
        guild_id = None
        try:
            _, guild_id = get_config()
        except RuntimeError:
            pass
        print_json(error_payload(command, guild_id, exc.error_type, str(exc), details=exc.details))
        return exc.exit_code
    except RuntimeError as exc:
        print_json(error_payload(command, None, "config_error", str(exc)))
        return 1
    except discord.DiscordException as exc:
        print_json(error_payload(command, None, "runtime_error", str(exc)))
        return 2
    except Exception as exc:
        print_json(error_payload(command, None, "internal_error", str(exc)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
