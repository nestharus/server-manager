import argparse
import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

import discord_cli


def run(coro):
    return asyncio.run(coro)


def async_iter(values):
    async def generator():
        for value in values:
            yield value

    return generator()


def require_public_handler(command):
    attr = f"fetch_{command.replace('-', '_')}"
    handler = getattr(discord_cli, attr, None)
    if handler is None:
        pytest.fail(f"discord_cli.{attr} is missing from the public API")
    if not inspect.iscoroutinefunction(handler):
        pytest.fail(f"discord_cli.{attr} must be an async handler")
    return handler


def make_member(
    *,
    member_id,
    username,
    tag,
    display_name,
    bot=False,
    nick=None,
    joined_at=None,
    roles=None,
):
    member = MagicMock()
    member.id = member_id
    member.name = username
    member.bot = bot
    member.display_name = display_name
    member.nick = nick
    member.joined_at = joined_at
    member.roles = roles or []
    member.__str__.return_value = tag
    return member


def make_channel(
    *,
    channel_id,
    name,
    channel_type,
    position=0,
    category=None,
    parent=None,
    topic=None,
    nsfw=False,
):
    channel = Mock()
    channel.id = channel_id
    channel.name = name
    channel.type = channel_type
    channel.position = position
    channel.category = category
    channel.parent = parent
    channel.topic = topic
    channel.nsfw = nsfw
    return channel


def make_activity_author(*, user_id, username=None, display_name=None, bot=True):
    author = MagicMock()
    author.id = user_id
    author.name = username or f"user-{user_id}"
    author.bot = bot
    author.display_name = display_name or author.name
    author.__str__.return_value = f"{author.name}#0001"
    return author


def make_activity_message(*, message_id, author_id, created_at, content=None, bot=True):
    message = Mock()
    message.id = message_id
    message.created_at = created_at
    message.edited_at = None
    message.author = make_activity_author(user_id=author_id, bot=bot)
    message.content = content or f"message-{message_id}"
    message.attachments = []
    message.embeds = []
    message.pinned = False
    message.tts = False
    message.type = "default"
    message.jump_url = f"https://discord.invalid/messages/{message_id}"
    return message


def make_history_channel(*, channel_id, name, messages=None, history_side_effect=None, history_capable=True):
    channel = Mock()
    channel.id = channel_id
    channel.name = name
    channel.history_capable = history_capable
    if history_side_effect is not None:
        channel.history = Mock(side_effect=history_side_effect)
    else:
        channel.history = Mock(return_value=async_iter(messages or []))
    return channel


def make_role(
    *,
    role_id,
    name,
    color,
    hoist,
    position,
    permissions,
    managed,
    mentionable,
    is_default,
    is_bot_managed,
    is_integration,
    is_premium_subscriber,
    created_at,
):
    role = Mock()
    role.id = role_id
    role.name = name
    role.color = Mock(value=color)
    role.hoist = hoist
    role.position = position
    role.permissions = Mock(value=permissions)
    role.managed = managed
    role.mentionable = mentionable
    role.created_at = created_at
    role.is_default = Mock(return_value=is_default)
    role.is_bot_managed = Mock(return_value=is_bot_managed)
    role.is_integration = Mock(return_value=is_integration)
    role.is_premium_subscriber = Mock(return_value=is_premium_subscriber)
    return role


@pytest.fixture
def parser():
    return discord_cli.build_parser()


@pytest.fixture
def guild_fixture():
    created_at = datetime(2022, 4, 1, 12, 30, tzinfo=timezone.utc)
    joined_at = datetime(2023, 1, 2, 8, 15, tzinfo=timezone.utc)
    role_created_at = datetime(2022, 5, 6, 9, 45, tzinfo=timezone.utc)

    everyone_role = make_role(
        role_id=1,
        name="@everyone",
        color=0,
        hoist=False,
        position=0,
        permissions=1,
        managed=False,
        mentionable=False,
        is_default=True,
        is_bot_managed=False,
        is_integration=False,
        is_premium_subscriber=False,
        created_at=role_created_at,
    )
    helper_role = make_role(
        role_id=10,
        name="Helper",
        color=65280,
        hoist=True,
        position=2,
        permissions=8,
        managed=False,
        mentionable=True,
        is_default=False,
        is_bot_managed=False,
        is_integration=False,
        is_premium_subscriber=False,
        created_at=role_created_at,
    )
    bot_role = make_role(
        role_id=20,
        name="Bots",
        color=1193046,
        hoist=False,
        position=1,
        permissions=16,
        managed=True,
        mentionable=False,
        is_default=False,
        is_bot_managed=True,
        is_integration=True,
        is_premium_subscriber=True,
        created_at=role_created_at,
    )

    owner = make_member(
        member_id=1,
        username="owner",
        tag="owner#1234",
        display_name="Owner",
        joined_at=joined_at,
        roles=[helper_role],
    )
    human = make_member(
        member_id=2,
        username="alice",
        tag="alice#5678",
        display_name="Alice",
        joined_at=joined_at,
        roles=[helper_role],
    )
    bot_one = make_member(
        member_id=3,
        username="ticketbot",
        tag="ticketbot#0001",
        display_name="HumilityTicketBot",
        bot=True,
        nick="Support Bot",
        joined_at=joined_at,
        roles=[bot_role],
    )
    bot_two = make_member(
        member_id=4,
        username="logger",
        tag="logger#0002",
        display_name="Logger",
        bot=True,
        joined_at=joined_at,
        roles=[bot_role, helper_role],
    )

    help_category = Mock()
    help_category.id = 100
    help_category.name = "Help"

    general = make_channel(
        channel_id=101,
        name="general",
        channel_type="text",
        position=1,
        topic="General chat",
    )
    support = make_channel(
        channel_id=102,
        name="Support Desk",
        channel_type="text",
        position=2,
        category=help_category,
        topic="Support intake",
    )
    voice = make_channel(
        channel_id=103,
        name="Voice",
        channel_type="voice",
        position=3,
    )
    thread = make_channel(
        channel_id=201,
        name="support followup",
        channel_type="public_thread",
        parent=support,
        category=help_category,
    )

    attachment = Mock()
    attachment.id = 301
    attachment.filename = "log.txt"
    attachment.content_type = "text/plain"
    attachment.size = 12
    attachment.url = "https://cdn.example/log.txt"

    embed = Mock()
    embed.title = "Status"
    embed.url = "https://example.invalid/status"
    embed.type = "rich"

    first_message = Mock()
    first_message.id = 401
    first_message.created_at = datetime(2024, 4, 1, 10, 0, tzinfo=timezone.utc)
    first_message.edited_at = None
    first_message.author = human
    first_message.content = "First message"
    first_message.attachments = [attachment]
    first_message.embeds = [embed]
    first_message.pinned = False
    first_message.tts = False
    first_message.type = "default"
    first_message.jump_url = "https://discord.invalid/messages/401"

    second_message = Mock()
    second_message.id = 402
    second_message.created_at = datetime(2024, 4, 1, 10, 5, tzinfo=timezone.utc)
    second_message.edited_at = None
    second_message.author = bot_one
    second_message.content = "Second message"
    second_message.attachments = []
    second_message.embeds = []
    second_message.pinned = True
    second_message.tts = False
    second_message.type = "default"
    second_message.jump_url = "https://discord.invalid/messages/402"

    general.history = Mock(return_value=async_iter([second_message, first_message]))

    integration_user = Mock()
    integration_user.id = 900
    integration_user.__str__ = Mock(return_value="support-bot#9999")

    integration_account = Mock()
    integration_account.id = "acct-1"
    integration_account.name = "support"

    integration = Mock()
    integration.id = 501
    integration.name = "Support"
    integration.type = "discord"
    integration.enabled = True
    integration.account = integration_account
    integration.user = integration_user
    integration.application_id = 777

    guild = Mock()
    guild.name = "Humility"
    guild.id = 900000000000000001
    guild.owner = owner
    guild.owner_id = owner.id
    guild.fetch_member = AsyncMock(return_value=owner)
    guild.member_count = 42
    guild.channels = [general, support, voice]
    guild.threads = [thread]
    guild.roles = [everyone_role, helper_role, bot_role]
    guild.members = [owner, human, bot_one, bot_two]
    guild.premium_tier = 2
    guild.premium_subscription_count = 5
    guild.created_at = created_at
    guild.unavailable = False
    guild.integrations = AsyncMock(return_value=[integration])
    guild.get_channel = Mock(side_effect=lambda channel_id: next((c for c in guild.channels if c.id == channel_id), None))
    guild.get_thread = Mock(side_effect=lambda thread_id: next((t for t in guild.threads if t.id == thread_id), None))

    return {
        "guild": guild,
        "owner": owner,
        "human": human,
        "bots": [bot_one, bot_two],
        "channels": {"general": general, "support": support, "voice": voice},
        "thread": thread,
        "messages": [first_message, second_message],
        "integration": integration,
        "roles": {
            "everyone": everyone_role,
            "helper": helper_role,
            "bot": bot_role,
        },
    }


def test_get_config_requires_discord_bot_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_GUILD_ID", "900000000000000001")

    with pytest.raises(RuntimeError, match="DISCORD_BOT_TOKEN"):
        discord_cli.get_config()


def test_get_config_requires_discord_guild_id(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_GUILD_ID"):
        discord_cli.get_config()


def test_get_config_requires_integer_discord_guild_id(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "not-an-int")

    with pytest.raises(RuntimeError, match="DISCORD_GUILD_ID"):
        discord_cli.get_config()


def test_json_default_serializes_datetime_to_iso8601():
    value = datetime(2026, 4, 12, 18, 0, 1, tzinfo=timezone.utc)

    assert discord_cli.json_default(value) == value.isoformat()


def test_json_default_rejects_unsupported_types():
    with pytest.raises(TypeError):
        discord_cli.json_default(object())


def test_build_parser_recognizes_all_contract_subcommands(parser):
    subcommands = set()
    for action in parser._actions:
        if getattr(action, "choices", None):
            subcommands.update(action.choices)

    assert subcommands == {
        "overview",
        "bots",
        "bot-activity",
        "channels",
        "find-channel",
        "read",
        "integrations",
        "roles",
    }


def test_build_parser_rejects_unknown_subcommands(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["unknown"])


def test_read_subcommand_accepts_channel_and_optional_limit(parser):
    parsed = parser.parse_args(["read", "general", "--limit", "25"])

    assert parsed.command == "read"
    assert parsed.channel == "general"
    assert parsed.limit == 25


def test_bot_activity_subparser_exists(parser):
    parsed = parser.parse_args(["bot-activity", "123", "--per-channel-limit", "25"])

    assert parsed.command == "bot-activity"
    assert parsed.bot_id == 123
    assert parsed.per_channel_limit == 25
    assert parsed.func is discord_cli.run_command


def test_bot_activity_handler_is_async():
    assert inspect.iscoroutinefunction(discord_cli.fetch_bot_activity)


def test_bot_activity_in_command_specs():
    assert "bot-activity" in discord_cli.command_specs()


def test_roles_subcommand_is_recognized(parser):
    parsed = parser.parse_args(["roles"])

    assert parsed.command == "roles"


def test_overview_handler_returns_expected_contract_fields(guild_fixture):
    handler = require_public_handler("overview")
    guild = guild_fixture["guild"]
    owner = guild_fixture["owner"]

    result = run(handler(guild, argparse.Namespace()))

    assert result["name"] == guild.name
    assert result["id"] == guild.id
    assert result["owner"] == {
        "id": owner.id,
        "name": str(owner),
        "display_name": owner.display_name,
    }
    assert result["member_count"] == guild.member_count
    assert result["channel_count"] == len(guild.channels)
    assert result["role_count"] == len(guild.roles)
    assert result["boost_tier"] == guild.premium_tier
    assert result["boost_count"] == guild.premium_subscription_count
    assert result["created_at"] == guild.created_at.isoformat()
    assert result["unavailable"] is False


def test_bots_handler_filters_members_by_bot_flag(guild_fixture):
    handler = require_public_handler("bots")
    guild = guild_fixture["guild"]
    expected_bots = guild_fixture["bots"]

    result = run(handler(guild, argparse.Namespace()))

    assert result["count"] == len(expected_bots)
    assert [entry["id"] for entry in result["bots"]] == [member.id for member in expected_bots]
    assert all(entry["id"] != guild_fixture["human"].id for entry in result["bots"])


def test_channels_handler_returns_channel_info(guild_fixture):
    handler = require_public_handler("channels")
    guild = guild_fixture["guild"]

    result = run(handler(guild, argparse.Namespace()))

    assert "channels" in result
    assert "threads" in result
    assert any(
        entry["id"] == guild_fixture["channels"]["general"].id
        and entry["name"] == guild_fixture["channels"]["general"].name
        and entry["type"] == str(guild_fixture["channels"]["general"].type)
        for entry in result["channels"]
    )


def test_find_channel_matches_substring_case_insensitively(guild_fixture):
    handler = require_public_handler("find-channel")
    guild = guild_fixture["guild"]

    result = run(handler(guild, argparse.Namespace(name="SUPPORT")))

    assert result["query"] == "SUPPORT"
    assert result["count"] == len(result["matches"])
    assert {match["name"] for match in result["matches"]} >= {"Support Desk", "support followup"}
    assert all("support" in match["name"].lower() for match in result["matches"])


def test_find_channel_returns_empty_list_when_no_match(guild_fixture):
    handler = require_public_handler("find-channel")
    guild = guild_fixture["guild"]

    result = run(handler(guild, argparse.Namespace(name="does-not-exist")))

    assert result["query"] == "does-not-exist"
    assert result["count"] == 0
    assert result["matches"] == []


def test_read_handler_returns_message_content_with_author_info(guild_fixture):
    handler = require_public_handler("read")
    guild = guild_fixture["guild"]
    general = guild_fixture["channels"]["general"]

    result = run(handler(guild, argparse.Namespace(channel="general", limit=2)))

    assert result["channel"]["id"] == general.id
    assert result["channel"]["name"] == general.name
    assert result["limit"] == 2
    assert result["message_count"] == 2
    assert [message["content"] for message in result["messages"]] == ["First message", "Second message"]
    assert result["messages"][0]["author"] == {
        "id": guild_fixture["human"].id,
        "name": str(guild_fixture["human"]),
        "display_name": guild_fixture["human"].display_name,
        "bot": False,
    }


def test_integrations_handler_returns_type_and_enabled_status(guild_fixture):
    handler = require_public_handler("integrations")
    guild = guild_fixture["guild"]
    integration = guild_fixture["integration"]

    result = run(handler(guild, argparse.Namespace()))

    assert result["count"] == 1
    assert result["integrations"][0]["id"] == integration.id
    assert result["integrations"][0]["type"] == integration.type
    assert result["integrations"][0]["enabled"] is True


def test_roles_handler_is_public_async(guild_fixture):
    handler = require_public_handler("roles")

    assert handler is not None


def test_roles_handler_returns_role_count(guild_fixture):
    handler = require_public_handler("roles")
    guild = guild_fixture["guild"]

    result = run(handler(guild, argparse.Namespace()))

    assert result["count"] == len(guild.roles)
    assert len(result["roles"]) == len(guild.roles)


def test_roles_handler_serializes_role_fields(guild_fixture):
    handler = require_public_handler("roles")
    guild = guild_fixture["guild"]
    helper_role = guild_fixture["roles"]["helper"]

    result = run(handler(guild, argparse.Namespace()))
    helper_entry = next(entry for entry in result["roles"] if entry["id"] == helper_role.id)

    assert helper_entry["id"] == helper_role.id
    assert isinstance(helper_entry["id"], int)
    assert helper_entry["name"] == helper_role.name
    assert isinstance(helper_entry["name"], str)
    assert helper_entry["color"] == helper_role.color.value
    assert isinstance(helper_entry["color"], int)
    assert helper_entry["hoist"] is helper_role.hoist
    assert isinstance(helper_entry["hoist"], bool)
    assert helper_entry["position"] == helper_role.position
    assert isinstance(helper_entry["position"], int)
    assert helper_entry["permissions"] == helper_role.permissions.value
    assert isinstance(helper_entry["permissions"], int)
    assert helper_entry["managed"] is helper_role.managed
    assert isinstance(helper_entry["managed"], bool)
    assert helper_entry["mentionable"] is helper_role.mentionable
    assert isinstance(helper_entry["mentionable"], bool)


def test_roles_handler_includes_boolean_helpers(guild_fixture):
    handler = require_public_handler("roles")
    guild = guild_fixture["guild"]
    everyone_role = guild_fixture["roles"]["everyone"]
    bot_role = guild_fixture["roles"]["bot"]

    result = run(handler(guild, argparse.Namespace()))
    role_entries = {entry["id"]: entry for entry in result["roles"]}

    everyone_entry = role_entries[everyone_role.id]
    assert everyone_entry["is_default"] is True
    assert isinstance(everyone_entry["is_default"], bool)
    assert everyone_entry["is_bot_managed"] is False
    assert isinstance(everyone_entry["is_bot_managed"], bool)
    assert everyone_entry["is_integration"] is False
    assert isinstance(everyone_entry["is_integration"], bool)
    assert everyone_entry["is_premium_subscriber"] is False
    assert isinstance(everyone_entry["is_premium_subscriber"], bool)

    bot_entry = role_entries[bot_role.id]
    assert bot_entry["is_default"] is False
    assert isinstance(bot_entry["is_default"], bool)
    assert bot_entry["is_bot_managed"] is True
    assert isinstance(bot_entry["is_bot_managed"], bool)
    assert bot_entry["is_integration"] is True
    assert isinstance(bot_entry["is_integration"], bool)
    assert bot_entry["is_premium_subscriber"] is True
    assert isinstance(bot_entry["is_premium_subscriber"], bool)


def test_roles_handler_serializes_created_at_iso8601(guild_fixture):
    handler = require_public_handler("roles")
    guild = guild_fixture["guild"]
    helper_role = guild_fixture["roles"]["helper"]

    result = run(handler(guild, argparse.Namespace()))
    helper_entry = next(entry for entry in result["roles"] if entry["id"] == helper_role.id)

    assert helper_entry["created_at"] == helper_role.created_at.isoformat()


def test_is_history_capable_text_channel():
    channel = Mock(spec=discord_cli.discord.TextChannel)

    assert discord_cli.is_history_capable_channel(channel) is True


def test_is_history_capable_voice_channel():
    channel = Mock(spec=discord_cli.discord.VoiceChannel)

    assert discord_cli.is_history_capable_channel(channel) is True


def test_is_history_capable_stage_channel():
    channel = Mock(spec=discord_cli.discord.StageChannel)

    assert discord_cli.is_history_capable_channel(channel) is True


def test_is_history_capable_thread():
    channel = Mock(spec=discord_cli.discord.Thread)

    assert discord_cli.is_history_capable_channel(channel) is True


def test_is_history_capable_category_excluded():
    channel = Mock(spec=discord_cli.discord.CategoryChannel)

    assert discord_cli.is_history_capable_channel(channel) is False


def test_is_history_capable_forum_excluded():
    channel = Mock(spec=discord_cli.discord.ForumChannel)

    assert discord_cli.is_history_capable_channel(channel) is False


def test_bot_activity_zero_results(monkeypatch):
    bot_id = 42
    other_message = make_activity_message(
        message_id=1001,
        author_id=9001,
        created_at=datetime(2024, 4, 2, 10, 0, tzinfo=timezone.utc),
    )
    eligible = make_history_channel(
        channel_id=101,
        name="general",
        messages=[other_message],
        history_capable=True,
    )
    ineligible = make_history_channel(
        channel_id=102,
        name="forum",
        messages=[],
        history_capable=False,
    )

    monkeypatch.setattr(discord_cli, "combined_channels", lambda guild: [eligible, ineligible])
    monkeypatch.setattr(
        discord_cli,
        "is_history_capable_channel",
        lambda channel: channel.history_capable,
    )

    result = run(
        discord_cli.fetch_bot_activity(
            Mock(),
            argparse.Namespace(bot_id=bot_id, per_channel_limit=100),
        )
    )

    eligible.history.assert_called_once_with(limit=100)
    ineligible.history.assert_not_called()
    assert result == {
        "bot_id": bot_id,
        "total_messages_seen": 0,
        "last_seen": None,
        "per_channel": [],
        "samples": [],
    }


def test_bot_activity_finds_messages(monkeypatch):
    bot_id = 42
    older = make_activity_message(
        message_id=1001,
        author_id=bot_id,
        created_at=datetime(2024, 4, 2, 9, 0, tzinfo=timezone.utc),
        content="older",
    )
    newest = make_activity_message(
        message_id=1002,
        author_id=bot_id,
        created_at=datetime(2024, 4, 2, 11, 0, tzinfo=timezone.utc),
        content="newest",
    )
    middle = make_activity_message(
        message_id=1003,
        author_id=bot_id,
        created_at=datetime(2024, 4, 2, 10, 0, tzinfo=timezone.utc),
        content="middle",
    )
    non_match = make_activity_message(
        message_id=1004,
        author_id=9001,
        created_at=datetime(2024, 4, 2, 12, 0, tzinfo=timezone.utc),
    )
    admin = make_history_channel(
        channel_id=201,
        name="admin-chat",
        messages=[newest, older, non_match],
    )
    logs = make_history_channel(
        channel_id=202,
        name="logs",
        messages=[middle],
    )

    monkeypatch.setattr(discord_cli, "combined_channels", lambda guild: [admin, logs])
    monkeypatch.setattr(discord_cli, "is_history_capable_channel", lambda channel: True)

    result = run(
        discord_cli.fetch_bot_activity(
            Mock(),
            argparse.Namespace(bot_id=bot_id, per_channel_limit=100),
        )
    )

    assert result["bot_id"] == bot_id
    assert result["total_messages_seen"] == 3
    assert result["last_seen"] == newest.created_at.isoformat()
    assert result["per_channel"] == [
        {
            "channel_id": admin.id,
            "channel_name": admin.name,
            "count": 2,
            "last_seen": newest.created_at.isoformat(),
        },
        {
            "channel_id": logs.id,
            "channel_name": logs.name,
            "count": 1,
            "last_seen": middle.created_at.isoformat(),
        },
    ]
    assert result["samples"] == [
        discord_cli.serialize_message(newest),
        discord_cli.serialize_message(middle),
        discord_cli.serialize_message(older),
    ]


def test_bot_activity_forbidden_channel_skipped(monkeypatch):
    bot_id = 42

    class FakeForbidden(Exception):
        pass

    allowed_message = make_activity_message(
        message_id=1001,
        author_id=bot_id,
        created_at=datetime(2024, 4, 2, 10, 0, tzinfo=timezone.utc),
    )
    allowed = make_history_channel(
        channel_id=301,
        name="allowed",
        messages=[allowed_message],
    )
    blocked = make_history_channel(
        channel_id=302,
        name="blocked",
        history_side_effect=FakeForbidden("no access"),
    )

    monkeypatch.setattr(discord_cli.discord, "Forbidden", FakeForbidden)
    monkeypatch.setattr(discord_cli, "combined_channels", lambda guild: [blocked, allowed])
    monkeypatch.setattr(discord_cli, "is_history_capable_channel", lambda channel: True)

    result = run(
        discord_cli.fetch_bot_activity(
            Mock(),
            argparse.Namespace(bot_id=bot_id, per_channel_limit=100),
        )
    )

    blocked.history.assert_called_once_with(limit=100)
    allowed.history.assert_called_once_with(limit=100)
    assert result["total_messages_seen"] == 1
    assert result["per_channel"] == [
        {
            "channel_id": allowed.id,
            "channel_name": allowed.name,
            "count": 1,
            "last_seen": allowed_message.created_at.isoformat(),
        }
    ]


def test_bot_activity_invalid_limit():
    with pytest.raises(discord_cli.CLIError):
        run(
            discord_cli.fetch_bot_activity(
                Mock(),
                argparse.Namespace(bot_id=42, per_channel_limit=0),
            )
        )


def test_bot_activity_samples_limited(monkeypatch):
    bot_id = 42
    messages = [
        make_activity_message(
            message_id=2000 + offset,
            author_id=bot_id,
            created_at=datetime(2024, 4, 2, 23 - offset, 0, tzinfo=timezone.utc),
        )
        for offset in range(12)
    ]
    channel = make_history_channel(
        channel_id=401,
        name="busy-bot",
        messages=messages,
    )

    monkeypatch.setattr(discord_cli, "combined_channels", lambda guild: [channel])
    monkeypatch.setattr(discord_cli, "is_history_capable_channel", lambda channel: True)

    result = run(
        discord_cli.fetch_bot_activity(
            Mock(),
            argparse.Namespace(bot_id=bot_id, per_channel_limit=100),
        )
    )

    assert result["total_messages_seen"] == 12
    assert len(result["samples"]) == 10
    assert result["samples"] == [discord_cli.serialize_message(message) for message in messages[:10]]


def test_bot_activity_per_channel_sorted(monkeypatch):
    bot_id = 42
    alpha = make_history_channel(
        channel_id=501,
        name="alpha",
        messages=[
            make_activity_message(
                message_id=3001,
                author_id=bot_id,
                created_at=datetime(2024, 4, 2, 10, 0, tzinfo=timezone.utc),
            ),
            make_activity_message(
                message_id=3002,
                author_id=bot_id,
                created_at=datetime(2024, 4, 2, 9, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    beta = make_history_channel(
        channel_id=502,
        name="beta",
        messages=[
            make_activity_message(
                message_id=3003,
                author_id=bot_id,
                created_at=datetime(2024, 4, 2, 11, 0, tzinfo=timezone.utc),
            ),
            make_activity_message(
                message_id=3004,
                author_id=bot_id,
                created_at=datetime(2024, 4, 2, 8, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    gamma = make_history_channel(
        channel_id=503,
        name="gamma",
        messages=[
            make_activity_message(
                message_id=3005,
                author_id=bot_id,
                created_at=datetime(2024, 4, 2, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )

    monkeypatch.setattr(discord_cli, "combined_channels", lambda guild: [gamma, alpha, beta])
    monkeypatch.setattr(discord_cli, "is_history_capable_channel", lambda channel: True)

    result = run(
        discord_cli.fetch_bot_activity(
            Mock(),
            argparse.Namespace(bot_id=bot_id, per_channel_limit=100),
        )
    )

    assert [entry["channel_id"] for entry in result["per_channel"]] == [
        beta.id,
        alpha.id,
        gamma.id,
    ]


def test_run_gateway_command_closes_client_on_success(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "900000000000000001")

    close_spy = AsyncMock()
    guild = Mock()
    guild.unavailable = False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self._events = {}

        def event(self, fn):
            self._events[fn.__name__] = fn
            return fn

        def get_guild(self, guild_id):
            assert guild_id == 900000000000000001
            return guild

        async def close(self):
            await close_spy()

        async def start(self, token, reconnect=False):
            assert token == "token"
            assert reconnect is False
            await self._events["on_ready"]()

    monkeypatch.setattr(discord_cli.discord, "Client", FakeClient)

    async def handler(client, resolved_guild):
        assert isinstance(client, FakeClient)
        assert resolved_guild is guild
        return {"status": "ok"}

    result = run(discord_cli.run_gateway_command(handler))

    assert result == {"status": "ok"}
    close_spy.assert_awaited_once()


def test_run_gateway_command_propagates_handler_errors_and_still_closes_client(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "900000000000000001")

    close_spy = AsyncMock()
    guild = Mock()
    guild.unavailable = False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self._events = {}

        def event(self, fn):
            self._events[fn.__name__] = fn
            return fn

        def get_guild(self, guild_id):
            assert guild_id == 900000000000000001
            return guild

        async def close(self):
            await close_spy()

        async def start(self, token, reconnect=False):
            await self._events["on_ready"]()

    monkeypatch.setattr(discord_cli.discord, "Client", FakeClient)

    async def handler(client, resolved_guild):
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        run(discord_cli.run_gateway_command(handler))

    close_spy.assert_awaited_once()


def test_run_gateway_command_raises_cli_error_on_gateway_timeout(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "900000000000000001")

    close_spy = AsyncMock()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self._events = {}

        def event(self, fn):
            self._events[fn.__name__] = fn
            return fn

        def get_guild(self, guild_id):
            return None

        async def close(self):
            await close_spy()

        async def start(self, token, reconnect=False):
            await asyncio.sleep(999)

    monkeypatch.setattr(discord_cli.discord, "Client", FakeClient)
    monkeypatch.setattr(discord_cli, "GATEWAY_TIMEOUT_SECONDS", 0.1)

    async def handler(client, resolved_guild):
        return {"status": "ok"}

    with pytest.raises(discord_cli.CLIError, match="timed out"):
        run(discord_cli.run_gateway_command(handler))

    close_spy.assert_awaited_once()


def _require_serializer(name: str) -> Callable[..., Any]:
    serializer = getattr(discord_cli, name, None)
    if serializer is None:
        pytest.fail(f"discord_cli.{name} is missing from the serialization contract")
    return serializer


def test_serialize_component_dispatches_action_row(monkeypatch):
    serializer = _require_serializer("serialize_component")
    row = MagicMock(spec=discord_cli.discord.ActionRow)
    dispatched = {"type": "action_row", "id": 111, "children": []}
    target = Mock(return_value=dispatched)

    monkeypatch.setattr(discord_cli, "serialize_action_row", target)

    assert serializer(row) == dispatched
    target.assert_called_once_with(row)


def test_serialize_component_dispatches_button(monkeypatch):
    serializer = _require_serializer("serialize_component")
    button = MagicMock(spec=discord_cli.discord.Button)
    dispatched = {"type": "button", "id": 222}
    target = Mock(return_value=dispatched)

    monkeypatch.setattr(discord_cli, "serialize_button", target)

    assert serializer(button) == dispatched
    target.assert_called_once_with(button)


def test_serialize_component_dispatches_select_menu(monkeypatch):
    serializer = _require_serializer("serialize_component")
    select_menu = MagicMock(spec=discord_cli.discord.SelectMenu)
    dispatched = {"type": "string_select", "id": 333}
    target = Mock(return_value=dispatched)

    monkeypatch.setattr(discord_cli, "serialize_select_menu", target)

    assert serializer(select_menu) == dispatched
    target.assert_called_once_with(select_menu)


def test_serialize_component_falls_back_for_unknown_component(monkeypatch):
    serializer = _require_serializer("serialize_component")
    component = MagicMock()
    dispatched = {"type": "action_row", "id": 444}
    target = Mock(return_value=dispatched)

    monkeypatch.setattr(discord_cli, "serialize_component_fallback", target)

    assert serializer(component) == dispatched
    target.assert_called_once_with(component)


def test_serialize_action_row_returns_type_id_and_children(monkeypatch):
    serializer = _require_serializer("serialize_action_row")
    first = MagicMock()
    second = MagicMock()
    row = MagicMock(spec=discord_cli.discord.ActionRow)
    row.type = discord_cli.discord.ComponentType.action_row
    row.id = 111
    row.children = [first, second]
    child_serializer = Mock(side_effect=[{"type": "button", "id": 222}, {"type": "string_select", "id": 333}])

    monkeypatch.setattr(discord_cli, "serialize_component", child_serializer)

    assert serializer(row) == {
        "type": "action_row",
        "id": 111,
        "children": [
            {"type": "button", "id": 222},
            {"type": "string_select", "id": 333},
        ],
    }
    assert [call.args[0] for call in child_serializer.call_args_list] == [first, second]


def test_serialize_button_interactive_button_shape(monkeypatch):
    serializer = _require_serializer("serialize_button")
    emoji = MagicMock(spec=discord_cli.discord.PartialEmoji)
    button = MagicMock(spec=discord_cli.discord.Button)
    button.type = discord_cli.discord.ComponentType.button
    button.id = 222
    button.custom_id = "ticket:create_general"
    button.label = "General Support"
    button.style = discord_cli.discord.ButtonStyle.primary
    button.emoji = emoji
    button.disabled = False
    button.url = None
    button.sku_id = None
    emoji_serializer = Mock(return_value={"name": "🎫", "id": None, "animated": False})

    monkeypatch.setattr(discord_cli, "serialize_partial_emoji", emoji_serializer)

    assert serializer(button) == {
        "type": "button",
        "id": 222,
        "custom_id": "ticket:create_general",
        "label": "General Support",
        "style": "primary",
        "emoji": {"name": "🎫", "id": None, "animated": False},
        "disabled": False,
        "url": None,
        "sku_id": None,
    }
    emoji_serializer.assert_called_once_with(emoji)


def test_serialize_button_link_button_shape(monkeypatch):
    serializer = _require_serializer("serialize_button")
    button = MagicMock(spec=discord_cli.discord.Button)
    button.type = discord_cli.discord.ComponentType.button
    button.id = 223
    button.custom_id = None
    button.label = "Open Docs"
    button.style = discord_cli.discord.ButtonStyle.link
    button.emoji = None
    button.disabled = True
    button.url = "https://example.com/docs"
    button.sku_id = None
    emoji_serializer = Mock(return_value=None)

    monkeypatch.setattr(discord_cli, "serialize_partial_emoji", emoji_serializer)

    assert serializer(button) == {
        "type": "button",
        "id": 223,
        "custom_id": None,
        "label": "Open Docs",
        "style": "link",
        "emoji": None,
        "disabled": True,
        "url": "https://example.com/docs",
        "sku_id": None,
    }
    emoji_serializer.assert_called_once_with(None)


def test_serialize_button_includes_sku_id_when_present(monkeypatch):
    serializer = _require_serializer("serialize_button")
    button = MagicMock(spec=discord_cli.discord.Button)
    button.type = discord_cli.discord.ComponentType.button
    button.id = 224
    button.custom_id = None
    button.label = "Premium Upgrade"
    button.style = discord_cli.discord.ButtonStyle.premium
    button.emoji = None
    button.disabled = False
    button.url = None
    button.sku_id = 987654321
    emoji_serializer = Mock(return_value=None)

    monkeypatch.setattr(discord_cli, "serialize_partial_emoji", emoji_serializer)

    result = serializer(button)

    assert result["sku_id"] == 987654321
    assert result["style"] == "premium"


def test_serialize_select_menu_returns_contract_shape(monkeypatch):
    serializer = _require_serializer("serialize_select_menu")
    first_option = MagicMock(spec=discord_cli.discord.SelectOption)
    second_option = MagicMock(spec=discord_cli.discord.SelectOption)
    first_default = MagicMock(spec=discord_cli.discord.SelectDefaultValue)
    second_default = MagicMock(spec=discord_cli.discord.SelectDefaultValue)
    menu = MagicMock(spec=discord_cli.discord.SelectMenu)
    menu.type = discord_cli.discord.ComponentType.string_select
    menu.id = 333
    menu.custom_id = "ticket:type"
    menu.placeholder = "Choose a ticket type"
    menu.min_values = 1
    menu.max_values = 2
    menu.disabled = False
    menu.options = [first_option, second_option]
    menu.channel_types = [
        discord_cli.discord.ChannelType.text,
        discord_cli.discord.ChannelType.voice,
    ]
    menu.default_values = [first_default, second_default]
    option_serializer = Mock(
        side_effect=[
            {"label": "General", "value": "general", "description": None, "emoji": None, "default": False},
            {"label": "Billing", "value": "billing", "description": "Payment questions", "emoji": None, "default": True},
        ]
    )
    default_value_serializer = Mock(
        side_effect=[
            {"id": 10, "type": "user"},
            {"id": 20, "type": "role"},
        ]
    )

    monkeypatch.setattr(discord_cli, "serialize_select_option", option_serializer)
    monkeypatch.setattr(discord_cli, "serialize_select_default_value", default_value_serializer)

    assert serializer(menu) == {
        "type": "string_select",
        "id": 333,
        "custom_id": "ticket:type",
        "placeholder": "Choose a ticket type",
        "min_values": 1,
        "max_values": 2,
        "disabled": False,
        "options": [
            {"label": "General", "value": "general", "description": None, "emoji": None, "default": False},
            {"label": "Billing", "value": "billing", "description": "Payment questions", "emoji": None, "default": True},
        ],
        "channel_types": ["text", "voice"],
        "default_values": [
            {"id": 10, "type": "user"},
            {"id": 20, "type": "role"},
        ],
    }
    assert [call.args[0] for call in option_serializer.call_args_list] == [first_option, second_option]
    assert [call.args[0] for call in default_value_serializer.call_args_list] == [first_default, second_default]


def test_serialize_select_option_returns_contract_shape(monkeypatch):
    serializer = _require_serializer("serialize_select_option")
    emoji = MagicMock(spec=discord_cli.discord.PartialEmoji)
    option = MagicMock(spec=discord_cli.discord.SelectOption)
    option.label = "General Support"
    option.value = "general"
    option.description = "Open a general support ticket"
    option.emoji = emoji
    option.default = True
    emoji_serializer = Mock(return_value={"name": "🎫", "id": None, "animated": False})

    monkeypatch.setattr(discord_cli, "serialize_partial_emoji", emoji_serializer)

    assert serializer(option) == {
        "label": "General Support",
        "value": "general",
        "description": "Open a general support ticket",
        "emoji": {"name": "🎫", "id": None, "animated": False},
        "default": True,
    }
    emoji_serializer.assert_called_once_with(emoji)


def test_serialize_partial_emoji_returns_none_for_none():
    serializer = _require_serializer("serialize_partial_emoji")

    assert serializer(None) is None


def test_serialize_partial_emoji_returns_name_id_and_animated():
    serializer = _require_serializer("serialize_partial_emoji")
    emoji = MagicMock(spec=discord_cli.discord.PartialEmoji)
    emoji.name = "party"
    emoji.id = 123456789
    emoji.animated = True

    assert serializer(emoji) == {
        "name": "party",
        "id": 123456789,
        "animated": True,
    }


def test_serialize_component_fallback_returns_type_and_id():
    serializer = _require_serializer("serialize_component_fallback")
    component = MagicMock()
    component.type = discord_cli.discord.ComponentType.action_row
    component.id = 999

    assert serializer(component) == {
        "type": "action_row",
        "id": 999,
    }


def test_serialize_message_includes_empty_components_list_when_missing():
    serializer = _require_serializer("serialize_message")
    message = make_activity_message(
        message_id=4001,
        author_id=42,
        created_at=datetime(2026, 4, 13, 1, 2, 3, tzinfo=timezone.utc),
        content="hello",
    )

    result = serializer(message)

    assert "components" in result
    assert result["components"] == []


def test_serialize_message_includes_serialized_components(monkeypatch):
    serializer = _require_serializer("serialize_message")
    first = MagicMock()
    second = MagicMock()
    message = make_activity_message(
        message_id=4002,
        author_id=42,
        created_at=datetime(2026, 4, 13, 1, 2, 3, tzinfo=timezone.utc),
        content="with components",
    )
    message.components = [first, second]
    component_serializer = Mock(
        side_effect=[
            {"type": "action_row", "id": 1, "children": []},
            {"type": "button", "id": 2},
        ]
    )

    monkeypatch.setattr(discord_cli, "serialize_component", component_serializer)

    result = serializer(message)

    assert result["components"] == [
        {"type": "action_row", "id": 1, "children": []},
        {"type": "button", "id": 2},
    ]
    assert [call.args[0] for call in component_serializer.call_args_list] == [first, second]


def test_serialize_select_default_value_returns_id_and_type():
    serializer = _require_serializer("serialize_select_default_value")
    value = MagicMock(spec=discord_cli.discord.SelectDefaultValue)
    value.id = 555
    value.type = discord_cli.discord.SelectDefaultValueType.user

    assert serializer(value) == {
        "id": 555,
        "type": "user",
    }
