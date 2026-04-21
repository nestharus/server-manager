from __future__ import annotations

import re
from typing import Any

import discord

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiUnreachableError,
)
from app.contracts.roster import RosterSyncEvent, RosterSyncResult


SERVICE_ACTOR_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "roster-syncer",
}


class RosterSyncFailure(Exception):
    def __init__(
        self,
        *,
        operation: str,
        failed_at_step: str,
        reason: str,
        error_type: str | None = None,
    ) -> None:
        self.operation = operation
        self.failed_at_step = failed_at_step
        self.reason = reason
        self.error_type = error_type
        super().__init__(reason)


def _resource_id(resource: Any) -> str:
    return str(getattr(resource, "id"))


def _slug(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def _iter(values: Any) -> tuple[Any, ...]:
    if values is None:
        return ()
    return tuple(values)


async def _resolve_member(guild: Any, user_id: str) -> Any:
    for member in _iter(getattr(guild, "members", [])):
        if _resource_id(member) == user_id:
            return member
    get_member = getattr(guild, "get_member", None)
    if callable(get_member):
        member = get_member(int(user_id))
        if member is not None:
            return member
    fetch_member = getattr(guild, "fetch_member", None)
    if callable(fetch_member):
        try:
            return await fetch_member(int(user_id))
        except (discord.NotFound, discord.HTTPException) as error:
            raise RosterSyncFailure(
                operation="resolve_member",
                failed_at_step="resolve_member",
                reason=str(error) or error.__class__.__name__,
                error_type=error.__class__.__name__,
            ) from error
    raise RosterSyncFailure(
        operation="resolve_member",
        failed_at_step="resolve_member",
        reason=f"member {user_id} was not found",
        error_type="MemberNotFound",
    )


def _find_role_by_id(guild: Any, role_id: str) -> Any | None:
    for role in _iter(getattr(guild, "roles", [])):
        if _resource_id(role) == role_id:
            return role
    return None


def _find_role_by_name(guild: Any, role_name: str) -> Any | None:
    role_slug = _slug(role_name)
    for role in _iter(getattr(guild, "roles", [])):
        candidate = str(getattr(role, "name", ""))
        if candidate == role_name or _slug(candidate) == role_slug:
            return role
        if role_slug and _slug(candidate).endswith(f"-{role_slug}"):
            return role
    return None


def _role_name_matches(role: Any, role_name: str) -> bool:
    candidate = str(getattr(role, "name", ""))
    role_slug = _slug(role_name)
    return (
        candidate == role_name
        or _slug(candidate) == role_slug
        or (bool(role_slug) and _slug(candidate).endswith(f"-{role_slug}"))
    )


def _desired_role_id(event: RosterSyncEvent) -> str | None:
    if event.chapter_discord_role_id:
        return event.chapter_discord_role_id
    role_ids = event.chapter_discord_resources.get("role_ids") or {}
    value = role_ids.get(event.chapter_role_name)
    return None if value is None else str(value)


def _resolve_role(guild: Any, event: RosterSyncEvent) -> tuple[Any, str]:
    desired_role_id = _desired_role_id(event)
    if desired_role_id is not None:
        role = _find_role_by_id(guild, desired_role_id)
        if role is not None and _role_name_matches(role, event.chapter_role_name):
            return role, desired_role_id
    role = _find_role_by_name(guild, event.chapter_role_name)
    if role is not None:
        return role, _resource_id(role)
    raise RosterSyncFailure(
        operation="resolve_role",
        failed_at_step="resolve_role",
        reason=f"role {event.chapter_role_name} was not found",
        error_type="RoleNotFound",
    )


def _has_role(member: Any, role_id: str) -> bool:
    return any(_resource_id(role) == role_id for role in _iter(getattr(member, "roles", [])))


def _reason(event: RosterSyncEvent) -> str:
    return (
        f"roster_entry={event.roster_entry_id} "
        f"transition={event.transition_id} "
        f"originating_actor={event.originating_actor_kind}:{event.originating_actor_id}"
    )


async def _record_sync_failure(
    api_client: Any,
    event: RosterSyncEvent,
    *,
    operation: str,
    failed_at_step: str,
    desired_role_id: str | None,
    reason: str,
    error_type: str | None,
) -> bool:
    if api_client is None:
        return False
    try:
        response = await api_client.call(
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/roster-entries/{event.roster_entry_id}/sync-failure",
                body={
                    "transition_id": str(event.transition_id),
                    "reason": reason,
                    "member_discord_user_id": event.member_discord_user_id,
                    "operation": operation,
                    "failed_at_step": failed_at_step,
                    "desired_discord_role_ids": ([] if desired_role_id is None else [desired_role_id]),
                    "error_type": error_type,
                    "originating_actor_kind": "service",
                    "originating_actor_id": "roster-syncer",
                },
                headers={
                    **SERVICE_ACTOR_HEADERS,
                    "If-Match": f'"{event.roster_entry_version}"',
                },
            )
        )
    except (ApiTransportError, ApiUnreachableError):
        return False
    return 200 <= response.status < 300


async def sync_roster(
    event: RosterSyncEvent,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> RosterSyncResult:
    if event.ack_deferred is not None:
        await event.ack_deferred()

    applied: list[str] = []
    skipped: list[str] = []
    desired_role_id: str | None = _desired_role_id(event)

    try:
        if guild is None:
            raise RosterSyncFailure(
                operation="resolve_member",
                failed_at_step="resolve_guild",
                reason="guild is not configured",
                error_type="GuildMissing",
            )
        member = await _resolve_member(guild, event.member_discord_user_id)
        role, desired_role_id = _resolve_role(guild, event)
        reason = _reason(event)
        if event.status == "removed":
            if not _has_role(member, desired_role_id):
                skipped.append(desired_role_id)
            else:
                await member.remove_roles(role, reason=reason)
                applied.append(desired_role_id)
        else:
            if _has_role(member, desired_role_id):
                skipped.append(desired_role_id)
            else:
                await member.add_roles(role, reason=reason)
                applied.append(desired_role_id)
        return RosterSyncResult(
            roster_entry_id=event.roster_entry_id,
            transition_id=str(event.transition_id),
            applied_role_ids=applied,
            skipped_role_ids=skipped,
        )
    except RosterSyncFailure as error:
        failure_recorded = await _record_sync_failure(
            api_client,
            event,
            operation=error.operation,
            failed_at_step=error.failed_at_step,
            desired_role_id=desired_role_id,
            reason=error.reason,
            error_type=error.error_type,
        )
        return RosterSyncResult(
            roster_entry_id=event.roster_entry_id,
            transition_id=str(event.transition_id),
            applied_role_ids=applied,
            skipped_role_ids=skipped,
            failure_recorded=failure_recorded,
        )
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as error:
        operation = "remove_roles" if event.status == "removed" else "add_roles"
        failure_recorded = await _record_sync_failure(
            api_client,
            event,
            operation=operation,
            failed_at_step=f"discord_{operation}",
            desired_role_id=desired_role_id,
            reason=str(error) or error.__class__.__name__,
            error_type=error.__class__.__name__,
        )
        return RosterSyncResult(
            roster_entry_id=event.roster_entry_id,
            transition_id=str(event.transition_id),
            applied_role_ids=applied,
            skipped_role_ids=skipped,
            failure_recorded=failure_recorded,
        )


__all__ = [
    "SERVICE_ACTOR_HEADERS",
    "sync_roster",
]
