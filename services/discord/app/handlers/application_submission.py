from __future__ import annotations

from typing import Any

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.contracts.application_submission import ApplicationSubmissionCommand
from app.contracts.interactions import InteractionEnvelope, InteractionResult


MEMBER_RESOLVE_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "discord-ticket-bot",
}


def build_user_actor_headers(member_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": member_id}


async def _api_call(api_client: Any, request: ApiTransportRequest) -> ApiTransportResponse:
    return await api_client.call(request)


async def resolve_member_id(api_client: Any, discord_user_id: str) -> str:
    response = await _api_call(
        api_client,
        ApiTransportRequest(
            method="GET",
            path=f"/api/v1/members/by-discord/{discord_user_id}",
            headers=MEMBER_RESOLVE_HEADERS,
        ),
    )
    if response.status >= 400 or not response.body:
        raise ApiTransportError(
            status=response.status,
            body=response.body,
            reason=f"member resolve returned status {response.status}",
        )
    return str(response.body["id"])


async def handle_application_submit(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None:
        return InteractionResult(success=False, response_text="Application intake is not configured.")

    command = ApplicationSubmissionCommand.model_validate(envelope.arguments)
    try:
        member_id = await resolve_member_id(api_client, envelope.actor_id)
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path="/api/v1/applications",
                body={
                    "applicant_id": member_id,
                    "scope": {
                        "scope_kind": command.scope_kind,
                        "scope_id": command.scope_id,
                    },
                    "responses": command.responses,
                    "client_application_id": envelope.interaction_id,
                },
                headers=build_user_actor_headers(member_id),
            ),
        )
    except (ApiTransportError, ApiUnreachableError):
        return InteractionResult(success=False, response_text="Application submission failed.")

    payload = response.body or {}
    if response.status == 201:
        return InteractionResult(
            success=True,
            response_text=f"Application {payload['id']} submitted.",
        )
    if response.status == 409 and payload.get("code") == "duplicate_application_create":
        application = payload.get("application") or {}
        return InteractionResult(
            success=True,
            response_text=f"Application {application.get('id')} already submitted.",
        )
    return InteractionResult(success=False, response_text="Application submission failed.")


__all__ = [
    "MEMBER_RESOLVE_HEADERS",
    "build_user_actor_headers",
    "handle_application_submit",
    "resolve_member_id",
]
