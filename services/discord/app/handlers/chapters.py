from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.contracts.api_transport import ApiTransportRequest, ApiTransportResponse
from app.contracts.chapters import ChapterProvisioningError
from app.contracts.interactions import InteractionEnvelope, InteractionResult


SERVICE_ACTOR_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "discord-provisioner",
}


def _slug(value: str) -> str:
    lowered = value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "chapter"


def derive_resource_names(chapter: dict[str, Any]) -> dict[str, Any]:
    prefix = _slug(str(chapter["name"]))
    snapshot = chapter["template_snapshot"]
    return {
        "category": f"{prefix}-chapter",
        "roles": {
            role["name"]: f"{prefix}-{_slug(role['name'])}"
            for role in snapshot.get("role_structure", [])
        },
        "channels": {
            channel["name"]: f"{prefix}-{_slug(channel['name'])}"
            for channel in snapshot.get("channel_structure", [])
        },
    }


def _iter(values: Any) -> Iterable[Any]:
    if values is None:
        return ()
    return values


def _find_by_name(values: Any, name: str) -> Any | None:
    for value in _iter(values):
        if getattr(value, "name", None) == name:
            return value
    return None


def _resource_id(resource: Any) -> str:
    return str(getattr(resource, "id"))


def check_required_bot_permissions(guild: Any) -> None:
    permissions = getattr(getattr(guild, "me", None), "guild_permissions", None)
    missing = [
        attr
        for attr in ("manage_channels", "manage_roles", "view_channel")
        if not bool(getattr(permissions, attr, False))
    ]
    if missing:
        raise ChapterProvisioningError(
            step="category",
            reason=f"missing bot permissions: {', '.join(missing)}",
        )


async def _api_call(api_client: Any, request: ApiTransportRequest, *, step: str) -> ApiTransportResponse:
    response = await api_client.call(request)
    if response.status >= 400:
        raise ChapterProvisioningError(
            step=step,  # type: ignore[arg-type]
            reason=f"API returned status {response.status}",
        )
    return response


def _etag(response: ApiTransportResponse) -> str:
    for key, value in response.headers.items():
        if key.lower() == "etag":
            return value
    raise ChapterProvisioningError(step="api_confirm", reason="API response missing ETag")


def _originating_body(envelope: InteractionEnvelope, **extra: Any) -> dict[str, Any]:
    return {
        **extra,
        "originating_actor_kind": "user",
        "originating_actor_id": envelope.actor_id,
    }


async def _patch_resources(
    api_client: Any,
    *,
    chapter_id: str,
    etag: str,
    resources: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    response = await _api_call(
        api_client,
        ApiTransportRequest(
            method="PATCH",
            path=f"/api/v1/chapters/{chapter_id}/discord-resources",
            body={"resources": resources},
            headers={**SERVICE_ACTOR_HEADERS, "If-Match": etag},
        ),
        step="api_confirm",
    )
    return response.body or {}, _etag(response)


async def _transition(
    api_client: Any,
    *,
    envelope: InteractionEnvelope,
    chapter_id: str,
    etag: str,
    to_state: str,
    reason: str,
) -> tuple[dict[str, Any], str]:
    response = await _api_call(
        api_client,
        ApiTransportRequest(
            method="POST",
            path=f"/api/v1/chapters/{chapter_id}/transitions",
            body=_originating_body(envelope, to_state=to_state, reason=reason),
            headers={**SERVICE_ACTOR_HEADERS, "If-Match": etag},
        ),
        step="transition_active" if to_state == "active" else "transition_provisioning",
    )
    return response.body or {}, _etag(response)


async def provision_chapter_handler(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    resolved_api_client = api_client or envelope.arguments.get("_api_client")
    resolved_guild = guild or envelope.arguments.get("_guild")
    chapter_id = str(envelope.arguments["chapter_id"])
    if resolved_api_client is None or resolved_guild is None:
        return InteractionResult(
            success=False,
            response_text="Chapter provisioning is not configured.",
        )

    latest_etag = ""
    try:
        check_required_bot_permissions(resolved_guild)
        response = await _api_call(
            resolved_api_client,
            ApiTransportRequest(
                method="GET",
                path=f"/api/v1/chapters/{chapter_id}",
                headers=SERVICE_ACTOR_HEADERS,
            ),
            step="fetch_chapter",
        )
        chapter = response.body or {}
        latest_etag = _etag(response)

        if chapter.get("state") in {"proposed", "provisioning_failed"}:
            chapter, latest_etag = await _transition(
                resolved_api_client,
                envelope=envelope,
                chapter_id=chapter_id,
                etag=latest_etag,
                to_state="provisioning",
                reason="Discord provisioning started",
            )
        elif chapter.get("state") == "provisioning":
            return InteractionResult(
                success=False,
                response_text=(
                    f"Chapter {chapter_id} is already being provisioned by another request."
                ),
            )
        elif chapter.get("state") == "active":
            return InteractionResult(
                success=True,
                response_text=f"Chapter {chapter_id} is already active.",
            )

        names = derive_resource_names(chapter)
        resources = chapter.get("discord_resources") or {
            "category_id": None,
            "role_ids": {},
            "channel_ids": {},
        }

        category = _find_by_name(getattr(resolved_guild, "categories", []), names["category"])
        if category is None:
            category = await resolved_guild.create_category(names["category"])
        resources["category_id"] = _resource_id(category)
        chapter, latest_etag = await _patch_resources(
            resolved_api_client,
            chapter_id=chapter_id,
            etag=latest_etag,
            resources={"category_id": resources["category_id"]},
        )
        resources = chapter["discord_resources"]

        for logical_name, discord_name in names["roles"].items():
            role = _find_by_name(getattr(resolved_guild, "roles", []), discord_name)
            if role is None:
                role = await resolved_guild.create_role(name=discord_name)
            resources.setdefault("role_ids", {})[logical_name] = _resource_id(role)
            chapter, latest_etag = await _patch_resources(
                resolved_api_client,
                chapter_id=chapter_id,
                etag=latest_etag,
                resources={"role_ids": {logical_name: _resource_id(role)}},
            )
            resources = chapter["discord_resources"]

        for logical_name, discord_name in names["channels"].items():
            category_channels = [
                channel
                for channel in getattr(resolved_guild, "channels", [])
                if getattr(channel, "category", None) == category
            ]
            channel = _find_by_name(category_channels, discord_name)
            if channel is None:
                if hasattr(resolved_guild, "create_text_channel"):
                    channel = await resolved_guild.create_text_channel(
                        name=discord_name,
                        category=category,
                    )
                else:
                    channel = await category.create_text_channel(discord_name)
            resources.setdefault("channel_ids", {})[logical_name] = _resource_id(channel)
            chapter, latest_etag = await _patch_resources(
                resolved_api_client,
                chapter_id=chapter_id,
                etag=latest_etag,
                resources={"channel_ids": {logical_name: _resource_id(channel)}},
            )
            resources = chapter["discord_resources"]

        await _transition(
            resolved_api_client,
            envelope=envelope,
            chapter_id=chapter_id,
            etag=latest_etag,
            to_state="active",
            reason="Discord provisioning completed",
        )
        return InteractionResult(
            success=True,
            response_text=f"Chapter {chapter_id} provisioned.",
        )
    except Exception as error:
        reason = str(error) or error.__class__.__name__
        if latest_etag:
            try:
                await _transition(
                    resolved_api_client,
                    envelope=envelope,
                    chapter_id=chapter_id,
                    etag=latest_etag,
                    to_state="provisioning_failed",
                    reason=reason,
                )
            except Exception:
                pass
        return InteractionResult(
            success=False,
            response_text=f"Chapter {chapter_id} provisioning failed: {reason}",
        )


__all__ = [
    "SERVICE_ACTOR_HEADERS",
    "check_required_bot_permissions",
    "derive_resource_names",
    "provision_chapter_handler",
]
