from __future__ import annotations

from typing import Any

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.contracts.application_review import ApplicationReviewCommand
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.handlers.application_submission import build_user_actor_headers, resolve_member_id


async def _api_call(api_client: Any, request: ApiTransportRequest) -> ApiTransportResponse:
    return await api_client.call(request)


def _etag(response: ApiTransportResponse) -> str:
    for key, value in response.headers.items():
        if key.lower() == "etag":
            return value
    raise RuntimeError("API response missing ETag")


async def _post_outcome(guild: Any | None, summary: str) -> None:
    if guild is None:
        return
    channel = getattr(guild, "application_review_channel", None)
    if channel is not None and hasattr(channel, "send"):
        await channel.send(content=summary)


async def _handle_application_review(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None,
    guild: Any | None,
    forced_action: str,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None:
        return InteractionResult(success=False, response_text="Application review is not configured.")

    command = ApplicationReviewCommand.model_validate(
        {**envelope.arguments, "action": forced_action}
    )
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
            return InteractionResult(success=False, response_text="Application review failed.")
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/applications/{command.application_id}/transitions",
                body={
                    "action": forced_action,
                    "notes": command.notes,
                    "decision_reason": command.decision_reason,
                },
                headers={**headers, "If-Match": _etag(current)},
            ),
        )
    except (ApiTransportError, ApiUnreachableError, RuntimeError):
        return InteractionResult(success=False, response_text="Application review failed.")

    payload = response.body or {}
    if response.status == 409 and payload.get("code") == "application_already_claimed":
        owner = payload.get("owner_id") or "another reviewer"
        return InteractionResult(
            success=False,
            response_text=f"Application already claimed by {owner}.",
        )
    if response.status == 412:
        return InteractionResult(
            success=False,
            response_text="Application changed. Retry the review action.",
        )
    if response.status >= 400:
        return InteractionResult(success=False, response_text="Application review failed.")

    summary = (
        f"Application {payload['id']} {forced_action} complete; state is {payload['state']}."
    )
    await _post_outcome(guild, summary)
    return InteractionResult(success=True, response_text=summary, ephemeral=False)


async def handle_application_claim(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    return await _handle_application_review(
        envelope,
        api_client=api_client,
        guild=guild,
        forced_action="claim",
    )


async def handle_application_approve(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    return await _handle_application_review(
        envelope,
        api_client=api_client,
        guild=guild,
        forced_action="approve",
    )


async def handle_application_deny(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    return await _handle_application_review(
        envelope,
        api_client=api_client,
        guild=guild,
        forced_action="deny",
    )


__all__ = [
    "handle_application_approve",
    "handle_application_claim",
    "handle_application_deny",
]
