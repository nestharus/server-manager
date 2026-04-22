from __future__ import annotations

from typing import Any

from app.contracts.api_transport import ApiUnreachableError
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.contracts.permissions import (
    DiscordChannelRoleSnapshotEntry,
    DiscordGuildRoleSnapshotEntry,
    DiscordPermissionSnapshotEntry,
)
from app.infrastructure.permission_client import (
    PermissionApiClient,
    PermissionApiConflictError,
    PermissionApiHttpError,
    PermissionApiPreconditionFailedError,
)


def _decimal_bits(value: int | None) -> str:
    if value is None:
        return "0"
    return str(int(value))


def _resolve_scope(
    envelope: InteractionEnvelope,
) -> tuple[str, str | None]:
    chapter_id = envelope.arguments.get("chapter")
    if chapter_id:
        return "chapter", str(chapter_id)
    return "global", None


def _iter(values: Any) -> list[Any]:
    if values is None:
        return []
    return list(values)


def _is_role(target: Any) -> bool:
    return getattr(target, "__class__", type(None)).__name__ == "Role" or hasattr(
        target, "permissions"
    ) and not hasattr(target, "bot")


def _channels_for_scope(
    guild: Any,
    scope_kind: str,
    scope_id: str | None,
) -> list[Any]:
    if scope_kind != "chapter":
        return []
    channels: list[Any] = []
    for channel in _iter(getattr(guild, "channels", [])):
        category = getattr(channel, "category", None)
        if category is not None and str(getattr(category, "id", "")) == scope_id:
            channels.append(channel)
            continue
        if str(getattr(channel, "id", "")) == scope_id:
            channels.append(channel)
    return channels


def _guild_role_entries(
    guild: Any,
) -> list[DiscordPermissionSnapshotEntry]:
    entries: list[DiscordPermissionSnapshotEntry] = []
    default_role = getattr(guild, "default_role", None)
    for role in _iter(getattr(guild, "roles", [])):
        if default_role is not None and role is default_role:
            continue
        permissions = getattr(role, "permissions", None)
        bits = getattr(permissions, "value", 0) if permissions is not None else 0
        entries.append(
            DiscordGuildRoleSnapshotEntry(
                kind="guild_role",
                role_id=str(role.id),
                permission_bits=_decimal_bits(bits),
            )
        )
    return entries


def _channel_role_entries(
    guild: Any,
    scope_kind: str,
    scope_id: str | None,
) -> list[DiscordPermissionSnapshotEntry]:
    entries: list[DiscordPermissionSnapshotEntry] = []
    default_role = getattr(guild, "default_role", None)
    default_role_id = (
        str(getattr(default_role, "id", ""))
        if default_role is not None
        else None
    )
    for channel in _channels_for_scope(guild, scope_kind, scope_id):
        overwrites = getattr(channel, "overwrites", None) or {}
        for target, overwrite in overwrites.items():
            if not _is_role(target):
                continue
            if default_role_id and str(target.id) == default_role_id:
                continue
            pair = overwrite.pair() if hasattr(overwrite, "pair") else (None, None)
            allow, deny = pair
            allow_value = getattr(allow, "value", 0) if allow is not None else 0
            deny_value = getattr(deny, "value", 0) if deny is not None else 0
            entries.append(
                DiscordChannelRoleSnapshotEntry(
                    kind="channel_role",
                    role_id=str(target.id),
                    channel_id=str(channel.id),
                    allow_bits=_decimal_bits(allow_value),
                    deny_bits=_decimal_bits(deny_value),
                )
            )
    return entries


def _build_snapshot(
    guild: Any,
    scope_kind: str,
    scope_id: str | None,
) -> list[DiscordPermissionSnapshotEntry]:
    entries = _guild_role_entries(guild)
    entries.extend(_channel_role_entries(guild, scope_kind, scope_id))
    return entries


def _ephemeral_error(message: str) -> InteractionResult:
    return InteractionResult(success=False, response_text=message)


async def handle_reconcile_permissions(
    envelope: InteractionEnvelope,
    *,
    permission_client: PermissionApiClient,
    guild: Any | None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if guild is None:
        return _ephemeral_error("Permission reconciliation requires a guild context.")

    scope_kind, scope_id = _resolve_scope(envelope)

    try:
        run = await permission_client.create_reconciliation_run(
            scope_kind=scope_kind,
            scope_id=scope_id,
            originating_actor_kind=envelope.actor_kind,
            originating_actor_id=envelope.actor_id,
        )
    except PermissionApiHttpError as error:
        return _ephemeral_error(
            f"Could not start reconciliation: {error.reason}"
        )
    except ApiUnreachableError as error:
        return _ephemeral_error(
            f"Could not start reconciliation: {error.reason}"
        )

    entries = _build_snapshot(guild, scope_kind, scope_id)

    try:
        result = await permission_client.submit_snapshot(
            run_id=run.id, entries=entries,
        )
    except PermissionApiPreconditionFailedError:
        return _ephemeral_error(
            "Reconciliation conflicted with a concurrent run; retry."
        )
    except PermissionApiConflictError as error:
        body = error.body or {}
        run_status: str | None = None
        if isinstance(body, dict):
            if isinstance(body.get("status"), str):
                run_status = body["status"]
            elif isinstance(body.get("detail"), dict):
                nested = body["detail"].get("status")
                if isinstance(nested, str):
                    run_status = nested
        if run_status == "reconciled":
            # Terminal idempotent replay: submit_snapshot on an already-
            # reconciled run is safe to report as success.
            result = run
        elif run_status == "failed":
            return _ephemeral_error(
                "Previous reconciliation run failed; retry with a new run."
            )
        else:
            return _ephemeral_error(
                f"Reconciliation conflict: run is in state "
                f"{run_status or 'unknown'}. Retry with a new run."
            )
    except PermissionApiHttpError as error:
        return _ephemeral_error(
            f"Snapshot submission failed: {error.reason}"
        )
    except ApiUnreachableError as error:
        return _ephemeral_error(
            f"Snapshot submission failed: {error.reason}"
        )

    drift_count = len(result.drift_ids)
    return InteractionResult(
        success=True,
        response_text=(
            f"Reconciliation run {result.id} complete "
            f"({drift_count} drift row(s))."
        ),
    )


__all__ = [
    "handle_reconcile_permissions",
]
