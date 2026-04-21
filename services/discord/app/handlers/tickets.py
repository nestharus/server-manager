from __future__ import annotations

import base64
from typing import Any
from uuid import UUID, uuid5

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.contracts.tickets import TicketOpenCommand, TicketTransitionCommand


SERVICE_ACTOR_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "discord-ticket-bot",
}
_CHANNEL_SLUG_LEN = 10
_DISCORD_NONCE_MAX_LEN = 25


def build_user_actor_headers(member_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": member_id}


def _ticket_channel_name(ticket_id: UUID) -> str:
    encoded = base64.b32encode(ticket_id.bytes).decode("ascii").lower()
    return f"ticket-{encoded[:_CHANNEL_SLUG_LEN]}"


def _message_nonce(message_id: UUID) -> str:
    return (
        base64.b32encode(message_id.bytes)
        .decode("ascii")
        .rstrip("=")[:_DISCORD_NONCE_MAX_LEN]
    )


def _transition_nonce(ticket_id: UUID, version: int) -> str:
    return _message_nonce(uuid5(ticket_id, f"transition:{version}"))


def _ticket_marker(ticket_id: str) -> str:
    return f"ticket_id={ticket_id}"


def _iter(values: Any) -> tuple[Any, ...]:
    if values is None:
        return ()
    return tuple(values)


def _find_channel_by_name(guild: Any, name: str) -> Any | None:
    for channel in _iter(getattr(guild, "channels", None)):
        if getattr(channel, "name", None) == name:
            return channel
    for thread in _iter(getattr(guild, "threads", None)):
        if getattr(thread, "name", None) == name:
            return thread
    return None


async def _api_call(api_client: Any, request: ApiTransportRequest) -> ApiTransportResponse:
    return await api_client.call(request)


def _etag(response: ApiTransportResponse) -> str:
    for key, value in response.headers.items():
        if key.lower() == "etag":
            return value
    raise RuntimeError("API response missing ETag")


async def _create_visible_ticket_channel(
    guild: Any,
    *,
    ticket_id: UUID,
    initial_message_id: UUID,
    initial_body: str,
) -> Any:
    channel_name = _ticket_channel_name(ticket_id)
    existing = _find_channel_by_name(guild, channel_name)
    if existing is not None:
        return existing

    topic = _ticket_marker(str(ticket_id))
    if hasattr(guild, "create_text_channel"):
        channel = await guild.create_text_channel(channel_name, topic=topic)
    elif hasattr(guild, "create_channel"):
        channel = await guild.create_channel(channel_name, topic=topic)
    else:
        raise RuntimeError("guild cannot create a text channel")

    if hasattr(channel, "send"):
        await channel.send(
            content=f"{topic}\n{initial_body}",
            nonce=_message_nonce(initial_message_id),
            enforce_nonce=True,
        )
    return channel


async def handle_ticket_open(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None or guild is None:
        return InteractionResult(success=False, response_text="Ticketing is not configured.")

    command = TicketOpenCommand.model_validate(envelope.arguments)
    request_body = {
        "category_id": command.category_id,
        "reporter_id": envelope.actor_id,
        "subject_id": command.subject_discord_user_id,
        "priority": "normal",
        "client_ticket_id": envelope.interaction_id,
        "initial_message": {
            "body_markdown": command.message,
            "visibility": "reporter_visible",
            "client_message_id": envelope.interaction_id,
            "author_actor_kind": "user",
            "author_actor_id": envelope.actor_id,
        },
        "originating_actor_kind": "user",
        "originating_actor_id": envelope.actor_id,
    }

    try:
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path="/api/v1/tickets",
                body=request_body,
                headers=SERVICE_ACTOR_HEADERS,
            ),
        )
    except (ApiTransportError, ApiUnreachableError):
        return InteractionResult(success=False, response_text="Ticket open failed.")

    payload = response.body or {}
    if response.status == 409 and payload.get("code") != "duplicate_ticket_create":
        return InteractionResult(success=False, response_text="Ticket open failed.")
    if response.status not in {201, 409}:
        return InteractionResult(success=False, response_text="Ticket open failed.")

    ticket = payload["ticket"]
    initial_message = payload["initial_message"]
    ticket_id = UUID(str(ticket["id"]))
    initial_message_id = UUID(str(initial_message["id"]))

    try:
        await _create_visible_ticket_channel(
            guild,
            ticket_id=ticket_id,
            initial_message_id=initial_message_id,
            initial_body=command.message,
        )
    except Exception:
        return InteractionResult(
            success=False,
            response_text=f"Ticket {ticket['id']} exists but Discord channel creation failed.",
        )

    return InteractionResult(success=True, response_text=f"Ticket {ticket['id']} ready.")


async def handle_ticket_transition(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None:
        return InteractionResult(success=False, response_text="Ticketing is not configured.")

    command = TicketTransitionCommand.model_validate(envelope.arguments)
    user_headers = build_user_actor_headers(envelope.actor_id)

    try:
        current_response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="GET",
                path=f"/api/v1/tickets/{command.ticket_id}",
                headers=user_headers,
            ),
        )
    except (ApiTransportError, ApiUnreachableError):
        return InteractionResult(success=False, response_text="Ticket transition failed.")

    try:
        transition_response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/tickets/{command.ticket_id}/transitions",
                body={
                    "action": command.action,
                    "to_state": command.to_state,
                    "reason": command.reason,
                    "resolution": command.resolution,
                    "owner_id": command.owner_id,
                    "priority": command.priority,
                    "originating_actor_kind": "user",
                    "originating_actor_id": envelope.actor_id,
                },
                headers={**user_headers, "If-Match": _etag(current_response)},
            ),
        )
    except ApiTransportError as error:
        body = error.body or {}
        if error.status == 412 and body.get("code") == "stale_ticket_version":
            return InteractionResult(
                success=False,
                response_text="Ticket changed. Retry the transition.",
            )
        if error.status == 409 and body.get("code") in {
            "invalid_ticket_transition",
            "ticket_transition_reason_required",
            "ticket_transition_resolution_required",
        }:
            return InteractionResult(success=False, response_text=body.get("message", "Transition denied."))
        return InteractionResult(success=False, response_text="Ticket transition failed.")
    except ApiUnreachableError:
        return InteractionResult(success=False, response_text="Ticket transition failed.")

    ticket = transition_response.body or {}
    ticket_id = UUID(str(ticket["id"]))
    summary = (
        f"Ticket {ticket['id']} transitioned via {command.action} to {ticket['state']}"
    )
    if guild is not None:
        channel = _find_channel_by_name(guild, _ticket_channel_name(ticket_id))
        if channel is not None and hasattr(channel, "send"):
            await channel.send(
                content=summary,
                nonce=_transition_nonce(ticket_id, int(ticket["version"])),
                enforce_nonce=True,
            )
    return InteractionResult(success=True, response_text=summary, ephemeral=False)
