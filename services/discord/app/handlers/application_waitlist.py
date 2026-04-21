from __future__ import annotations

from typing import Any

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.contracts.application_waitlist import (
    ApplicationReactivateCommand,
    ApplicationWaitlistCommand,
)
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.handlers.application_submission import build_user_actor_headers, resolve_member_id


async def _api_call(api_client: Any, request: ApiTransportRequest) -> ApiTransportResponse:
    return await api_client.call(request)


def _etag(response: ApiTransportResponse) -> str:
    for key, value in response.headers.items():
        if key.lower() == "etag":
            return value
    raise RuntimeError("API response missing ETag")


async def _post_waitlist_status(guild: Any | None, summary: str) -> None:
    if guild is None:
        return
    channel = getattr(guild, "application_status_channel", None)
    if channel is None:
        channel = getattr(guild, "application_review_channel", None)
    if channel is not None and hasattr(channel, "send"):
        await channel.send(content=summary)


async def handle_application_waitlist(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None:
        return InteractionResult(success=False, response_text="Application waitlist is not configured.")

    command = ApplicationWaitlistCommand.model_validate(envelope.arguments)
    try:
        member_id = await resolve_member_id(api_client, envelope.actor_id)
        headers = build_user_actor_headers(member_id)
        current = await _api_call(
            api_client,
            ApiTransportRequest(
                method="GET",
                path=f"/api/v1/applications/{command.application_id}",
                headers=headers,
            ),
        )
        if current.status >= 400:
            return InteractionResult(success=False, response_text="Application waitlist failed.")
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/applications/{command.application_id}/waitlist",
                body={
                    "reason": command.reason,
                    "originating_actor_kind": "user",
                    "originating_actor_id": member_id,
                },
                headers={**headers, "If-Match": _etag(current)},
            ),
        )
    except (ApiTransportError, ApiUnreachableError, RuntimeError):
        return InteractionResult(success=False, response_text="Application waitlist failed.")

    if response.status == 412:
        return InteractionResult(
            success=False,
            response_text="Application changed. Retry the waitlist request.",
        )
    if response.status >= 400:
        return InteractionResult(success=False, response_text="Application waitlist failed.")

    payload = response.body or {}
    summary = f"Application {payload['id']} has been waitlisted."
    await _post_waitlist_status(guild, summary)
    return InteractionResult(success=True, response_text=summary)


async def handle_application_reactivate(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,  # noqa: ARG001 - kept for command registration symmetry
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None:
        return InteractionResult(success=False, response_text="Application reactivate is not configured.")

    command = ApplicationReactivateCommand.model_validate(envelope.arguments)
    try:
        member_id = await resolve_member_id(api_client, envelope.actor_id)
        headers = build_user_actor_headers(member_id)
        current = await _api_call(
            api_client,
            ApiTransportRequest(
                method="GET",
                path=f"/api/v1/applications/{command.application_id}",
                headers=headers,
            ),
        )
        if current.status >= 400:
            return InteractionResult(success=False, response_text="Application reactivate failed.")
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/applications/{command.application_id}/reactivate",
                body={
                    "new_owner_id": command.new_owner_id,
                    "reason": command.reason,
                    "originating_actor_kind": "user",
                    "originating_actor_id": member_id,
                },
                headers={**headers, "If-Match": _etag(current)},
            ),
        )
    except (ApiTransportError, ApiUnreachableError, RuntimeError):
        return InteractionResult(success=False, response_text="Application reactivate failed.")

    if response.status == 412:
        return InteractionResult(
            success=False,
            response_text="Application changed. Retry the reactivate request.",
        )
    if response.status >= 400:
        return InteractionResult(success=False, response_text="Application reactivate failed.")

    payload = response.body or {}
    return InteractionResult(
        success=True,
        response_text=f"Application {payload['id']} reactivated.",
    )


__all__ = [
    "handle_application_reactivate",
    "handle_application_waitlist",
]
