import asyncio
import importlib
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

try:
    import discord
except ModuleNotFoundError:  # pragma: no cover - local fallback for collection-only environments
    class _NotFound(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)

    discord = SimpleNamespace(
        ChannelType=SimpleNamespace(
            private_thread="private_thread",
            public_thread="public_thread",
        ),
        NotFound=_NotFound,
    )


def run(coro):
    return asyncio.run(coro)


def import_claim_module():
    try:
        return importlib.import_module("daemon.claim")
    except Exception as exc:  # pragma: no cover - import failures should fail loudly
        pytest.fail(f"Could not import daemon.claim: {exc!r}")


@pytest.fixture
def claim_module():
    return import_claim_module()


def require_handler(module, *names):
    for name in names:
        handler = getattr(module, name, None)
        if handler is not None:
            if not inspect.iscoroutinefunction(handler):
                pytest.fail(f"daemon.claim.{name} must be an async handler")
            return handler
    joined = ", ".join(f"daemon.claim.{name}" for name in names)
    pytest.fail(f"Missing expected claim helper. Tried: {joined}")


def call_preclaim(handler, *, thread, requester, handler_members):
    return run(handler(thread, requester=requester, handler_members=handler_members))


def call_claim(handler, *, thread, claimer, requester, guild):
    kwargs = {"claimer": claimer, "requester": requester}
    if "guild" in inspect.signature(handler).parameters:
        kwargs["guild"] = guild
    return run(handler(thread, **kwargs))


def make_snowflake(user_id):
    return SimpleNamespace(id=user_id)


def make_member(user_id, *, administrator=False, bot=False):
    member = MagicMock()
    member.id = user_id
    member.bot = bot
    member.guild_permissions = SimpleNamespace(administrator=administrator)
    return member


def make_thread_member(user_id):
    member = Mock()
    member.id = user_id
    return member


def make_thread(*, explicit_member_ids, guild, private=True):
    thread = MagicMock()
    thread.id = 777001
    thread.type = (
        discord.ChannelType.private_thread
        if private
        else discord.ChannelType.public_thread
    )
    thread.is_private = Mock(return_value=private)
    thread.fetch_members = AsyncMock(
        return_value=[make_thread_member(user_id) for user_id in explicit_member_ids]
    )
    thread.add_user = AsyncMock()
    thread.remove_user = AsyncMock()
    thread.guild = guild
    thread.me = getattr(guild, "me", None)
    thread.members = []
    return thread


def awaited_ids(async_mock):
    return sorted(call.args[0].id for call in async_mock.await_args_list)


def make_not_found():
    response = MagicMock()
    response.status = 404
    response.reason = "Not Found"
    return discord.NotFound(response, {"message": "Unknown Member", "code": 10007})


def test_public_api_matches_claim_contract(claim_module):
    assert hasattr(claim_module, "ClaimVisibilityResult")
    assert is_dataclass(claim_module.ClaimVisibilityResult)

    assert [field.name for field in fields(claim_module.ClaimVisibilityResult)] == [
        "thread_id",
        "member_ids_before",
        "member_ids_after",
        "added_member_ids",
        "removed_member_ids",
        "preserved_admin_ids",
        "unresolved_member_ids",
    ]

    result = claim_module.ClaimVisibilityResult(
        thread_id=1,
        member_ids_before=(3, 2, 1),
        member_ids_after=(1, 2, 3),
        added_member_ids=(1,),
        removed_member_ids=(3,),
        preserved_admin_ids=(2,),
        unresolved_member_ids=(4,),
    )
    with pytest.raises(FrozenInstanceError):
        result.thread_id = 2

    require_handler(claim_module, "ensure_preclaim_visibility", "populate_thread")
    require_handler(claim_module, "execute_claim_visibility", "claim_thread")


def test_preclaim_adds_requester_and_missing_handlers_without_removals(claim_module):
    preclaim = require_handler(
        claim_module, "ensure_preclaim_visibility", "populate_thread"
    )
    guild = MagicMock()
    guild.me = make_member(999, bot=True)
    requester = make_snowflake(101)
    existing_handler = make_snowflake(201)
    missing_handler = make_snowflake(202)
    duplicate_handler = make_snowflake(202)
    thread = make_thread(explicit_member_ids=[301, 201], guild=guild, private=True)

    result = call_preclaim(
        preclaim,
        thread=thread,
        requester=requester,
        handler_members=[
            existing_handler,
            missing_handler,
            duplicate_handler,
            requester,
        ],
    )

    assert awaited_ids(thread.add_user) == [101, 202]
    thread.remove_user.assert_not_awaited()

    assert result.thread_id == thread.id
    assert result.member_ids_before == (201, 301)
    assert result.member_ids_after == (101, 201, 202, 301)
    assert result.added_member_ids == (101, 202)
    assert result.removed_member_ids == ()
    assert result.preserved_admin_ids == ()
    assert result.unresolved_member_ids == ()


def test_preclaim_uses_fetch_members_as_authoritative_membership(claim_module):
    preclaim = require_handler(
        claim_module, "ensure_preclaim_visibility", "populate_thread"
    )
    guild = MagicMock()
    guild.me = make_member(999, bot=True)
    requester = make_snowflake(101)
    handler_member = make_snowflake(201)
    thread = make_thread(explicit_member_ids=[], guild=guild, private=True)
    thread.members = [make_thread_member(101), make_thread_member(201)]

    result = call_preclaim(
        preclaim,
        thread=thread,
        requester=requester,
        handler_members=[handler_member],
    )

    assert awaited_ids(thread.add_user) == [101, 201]
    assert result.member_ids_before == ()
    assert result.member_ids_after == (101, 201)
    assert result.added_member_ids == (101, 201)


def test_claim_narrows_thread_to_claimer_requester_admins_and_bot(claim_module):
    claim = require_handler(
        claim_module, "execute_claim_visibility", "claim_thread"
    )
    bot_member = make_member(900, bot=True)
    requester = make_member(100)
    claimer = make_member(200)
    admin_member = make_member(300, administrator=True)
    regular_member = make_member(400)
    unresolved_id = 500

    guild = MagicMock()
    guild.me = bot_member
    guild.get_member.side_effect = lambda user_id: {
        900: bot_member,
        400: regular_member,
    }.get(user_id)

    async def fetch_member(user_id):
        if user_id == 300:
            return admin_member
        if user_id == unresolved_id:
            raise make_not_found()
        raise AssertionError(f"Unexpected fetch_member({user_id})")

    guild.fetch_member = AsyncMock(side_effect=fetch_member)

    thread = make_thread(
        explicit_member_ids=[500, 400, 900, 300],
        guild=guild,
        private=True,
    )
    thread.members = [make_thread_member(100), make_thread_member(200)]

    result = call_claim(
        claim,
        thread=thread,
        claimer=claimer,
        requester=requester,
        guild=guild,
    )

    assert awaited_ids(thread.add_user) == [100, 200]
    assert awaited_ids(thread.remove_user) == [400, 500]
    assert awaited_ids(guild.fetch_member) == [300, 500]

    assert result.thread_id == thread.id
    assert result.member_ids_before == (300, 400, 500, 900)
    assert result.member_ids_after == (100, 200, 300, 900)
    assert result.added_member_ids == (100, 200)
    assert result.removed_member_ids == (400, 500)
    assert result.preserved_admin_ids == (300,)
    assert result.unresolved_member_ids == (500,)


def test_claim_is_idempotent_when_thread_is_already_narrowed(claim_module):
    claim = require_handler(
        claim_module, "execute_claim_visibility", "claim_thread"
    )
    bot_member = make_member(900, bot=True)
    requester = make_member(100)
    claimer = make_member(200)
    admin_member = make_member(300, administrator=True)

    guild = MagicMock()
    guild.me = bot_member
    guild.get_member.side_effect = lambda user_id: {
        300: admin_member,
        900: bot_member,
    }.get(user_id)
    guild.fetch_member = AsyncMock()

    thread = make_thread(
        explicit_member_ids=[300, 200, 900, 100],
        guild=guild,
        private=True,
    )

    result = call_claim(
        claim,
        thread=thread,
        claimer=claimer,
        requester=requester,
        guild=guild,
    )

    thread.add_user.assert_not_awaited()
    thread.remove_user.assert_not_awaited()
    guild.fetch_member.assert_not_awaited()

    assert result.member_ids_before == (100, 200, 300, 900)
    assert result.member_ids_after == (100, 200, 300, 900)
    assert result.added_member_ids == ()
    assert result.removed_member_ids == ()
    assert result.preserved_admin_ids == (300,)
    assert result.unresolved_member_ids == ()


@pytest.mark.parametrize(
    ("helper_names", "invoker"),
    [
        (
            ("ensure_preclaim_visibility", "populate_thread"),
            lambda handler, thread, guild: call_preclaim(
                handler,
                thread=thread,
                requester=make_snowflake(101),
                handler_members=[make_snowflake(201)],
            ),
        ),
        (
            ("execute_claim_visibility", "claim_thread"),
            lambda handler, thread, guild: call_claim(
                handler,
                thread=thread,
                claimer=make_member(200),
                requester=make_member(100),
                guild=guild,
            ),
        ),
    ],
)
def test_public_threads_are_rejected(helper_names, invoker, claim_module):
    handler = require_handler(claim_module, *helper_names)
    guild = MagicMock()
    guild.me = make_member(900, bot=True)
    thread = make_thread(explicit_member_ids=[100, 200], guild=guild, private=False)

    with pytest.raises(ValueError):
        invoker(handler, thread, guild)

    thread.fetch_members.assert_not_awaited()
    thread.add_user.assert_not_awaited()
    thread.remove_user.assert_not_awaited()
