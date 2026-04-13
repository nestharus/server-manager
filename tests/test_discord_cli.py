import argparse
import asyncio
import inspect
from datetime import datetime, timezone
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


@pytest.fixture
def parser():
    return discord_cli.build_parser()


@pytest.fixture
def guild_fixture():
    created_at = datetime(2022, 4, 1, 12, 30, tzinfo=timezone.utc)
    joined_at = datetime(2023, 1, 2, 8, 15, tzinfo=timezone.utc)

    helper_role = Mock()
    helper_role.id = 10
    helper_role.name = "Helper"

    bot_role = Mock()
    bot_role.id = 20
    bot_role.name = "Bots"

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
    guild.roles = [helper_role, bot_role]
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
        "channels",
        "find-channel",
        "read",
        "integrations",
    }


def test_build_parser_rejects_unknown_subcommands(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["unknown"])


def test_read_subcommand_accepts_channel_and_optional_limit(parser):
    parsed = parser.parse_args(["read", "general", "--limit", "25"])

    assert parsed.command == "read"
    assert parsed.channel == "general"
    assert parsed.limit == 25


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
