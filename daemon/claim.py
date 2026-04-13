"""Private-thread claim visibility helpers for the Humility daemon.

This module only reconciles explicit membership on private Discord
threads. It does not manage parent-channel permissions, workflow state,
or database updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Collection

try:
    import discord
except ModuleNotFoundError:  # pragma: no cover - fallback for test collection
    class _NotFound(Exception):
        pass

    discord = SimpleNamespace(
        ChannelType=SimpleNamespace(
            private_thread="private_thread",
            public_thread="public_thread",
        ),
        NotFound=_NotFound,
    )


@dataclass(frozen=True)
class ClaimVisibilityResult:
    thread_id: int
    member_ids_before: tuple[int, ...]
    member_ids_after: tuple[int, ...]
    added_member_ids: tuple[int, ...]
    removed_member_ids: tuple[int, ...]
    preserved_admin_ids: tuple[int, ...]
    unresolved_member_ids: tuple[int, ...]


async def ensure_preclaim_visibility(
    thread: "discord.Thread",
    *,
    requester: "discord.abc.Snowflake",
    handler_members: Collection["discord.abc.Snowflake"],
) -> ClaimVisibilityResult:
    _require_private_thread(thread)

    explicit_members = await thread.fetch_members()
    member_ids_before = _sorted_ids(member.id for member in explicit_members)
    existing_ids = set(member_ids_before)

    target_members = _dedupe_members([requester, *handler_members])
    added_members = [
        target_members[member_id]
        for member_id in sorted(target_members)
        if member_id not in existing_ids
    ]
    for member in added_members:
        await thread.add_user(member)

    added_member_ids = _sorted_ids(member.id for member in added_members)
    member_ids_after = _sorted_ids((*member_ids_before, *added_member_ids))
    return ClaimVisibilityResult(
        thread_id=thread.id,
        member_ids_before=member_ids_before,
        member_ids_after=member_ids_after,
        added_member_ids=added_member_ids,
        removed_member_ids=(),
        preserved_admin_ids=(),
        unresolved_member_ids=(),
    )


async def execute_claim_visibility(
    thread: "discord.Thread",
    *,
    requester: "discord.abc.Snowflake",
    claimer: "discord.abc.Snowflake",
) -> ClaimVisibilityResult:
    _require_private_thread(thread)

    guild = thread.guild
    explicit_members = await thread.fetch_members()
    member_ids_before = _sorted_ids(member.id for member in explicit_members)
    existing_ids = set(member_ids_before)

    required_members = _dedupe_members([requester, claimer])
    added_members = [
        required_members[member_id]
        for member_id in sorted(required_members)
        if member_id not in existing_ids
    ]
    for member in added_members:
        await thread.add_user(member)

    preserved_admin_ids: list[int] = []
    unresolved_member_ids: list[int] = []
    bot_id = _get_bot_id(thread, guild)
    keep_ids = set(required_members)
    if bot_id is not None and bot_id in existing_ids:
        keep_ids.add(bot_id)

    removable_members: list[Any] = []
    for member_id in member_ids_before:
        resolved_member = await _resolve_member(
            guild,
            member_id,
            requester=requester,
            claimer=claimer,
        )
        if resolved_member is None:
            unresolved_member_ids.append(member_id)
        elif _is_admin_member(resolved_member):
            preserved_admin_ids.append(member_id)
            keep_ids.add(member_id)
            continue

        if member_id not in keep_ids:
            removable_members.append(resolved_member or _snowflake(member_id))

    for member in removable_members:
        await thread.remove_user(member)

    added_member_ids = _sorted_ids(member.id for member in added_members)
    removed_member_ids = _sorted_ids(member.id for member in removable_members)
    member_ids_after = _sorted_ids(
        member_id
        for member_id in (*member_ids_before, *added_member_ids)
        if member_id not in set(removed_member_ids)
    )
    return ClaimVisibilityResult(
        thread_id=thread.id,
        member_ids_before=member_ids_before,
        member_ids_after=member_ids_after,
        added_member_ids=added_member_ids,
        removed_member_ids=removed_member_ids,
        preserved_admin_ids=_sorted_ids(preserved_admin_ids),
        unresolved_member_ids=_sorted_ids(unresolved_member_ids),
    )


def _require_private_thread(thread: Any) -> None:
    is_private = getattr(thread, "is_private", None)
    if callable(is_private):
        if is_private():
            return
        raise ValueError("Claim visibility helpers require a private thread.")

    if getattr(thread, "type", None) == discord.ChannelType.private_thread:
        return
    raise ValueError("Claim visibility helpers require a private thread.")


def _dedupe_members(members: Collection[Any]) -> dict[int, Any]:
    deduped: dict[int, Any] = {}
    for member in members:
        deduped.setdefault(member.id, member)
    return deduped


async def _resolve_member(
    guild: Any,
    member_id: int,
    *,
    requester: Any,
    claimer: Any,
) -> Any | None:
    for candidate in (requester, claimer):
        if getattr(candidate, "id", None) == member_id and _looks_like_member(candidate):
            return candidate

    cached_member = guild.get_member(member_id)
    if cached_member is not None:
        return cached_member

    try:
        return await guild.fetch_member(_member_lookup_id(member_id))
    except Exception as exc:
        if _is_not_found_error(exc):
            return None
        raise


def _looks_like_member(candidate: Any) -> bool:
    return hasattr(candidate, "guild_permissions")


def _is_admin_member(member: Any) -> bool:
    permissions = getattr(member, "guild_permissions", None)
    return bool(getattr(permissions, "administrator", False))


def _is_not_found_error(exc: Exception) -> bool:
    if isinstance(exc, discord.NotFound):
        return True
    return exc.__class__.__name__ in {"NotFound", "_NotFound"}


def _get_bot_id(thread: Any, guild: Any) -> int | None:
    bot_member = getattr(thread, "me", None) or getattr(guild, "me", None)
    return getattr(bot_member, "id", None)


def _snowflake(member_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=member_id)


class _MemberLookupId(int):
    @property
    def id(self) -> int:
        return int(self)


def _member_lookup_id(member_id: int) -> _MemberLookupId:
    return _MemberLookupId(member_id)


def _sorted_ids(member_ids: Collection[int]) -> tuple[int, ...]:
    return tuple(sorted(member_ids))
