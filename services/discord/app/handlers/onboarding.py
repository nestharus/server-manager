from __future__ import annotations

from typing import Any

from app.contracts.api_transport import ApiTransportRequest, ApiTransportResponse
from app.contracts.onboarding import MemberJoinEvent, MemberJoinOutcomeRead


SERVICE_ACTOR_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "member-onboarder",
}


class MemberOnboardingError(Exception):
    def __init__(self, *, step: str, status: int, body: dict[str, Any] | None) -> None:
        self.step = step
        self.status = status
        self.body = body
        super().__init__(f"{step} failed with API status {status}")


async def _api_call(
    api_client: Any,
    request: ApiTransportRequest,
    *,
    step: str,
) -> ApiTransportResponse:
    response = await api_client.call(request)
    if response.status >= 400:
        raise MemberOnboardingError(
            step=step,
            status=response.status,
            body=response.body,
        )
    return response


def _originating_body(event: MemberJoinEvent, **extra: Any) -> dict[str, Any]:
    return {
        **extra,
        "originating_actor_kind": event.originating_actor_kind,
        "originating_actor_id": event.originating_actor_id,
    }


def _signals_body(event: MemberJoinEvent) -> dict[str, Any]:
    return _originating_body(
        event,
        **event.signals.model_dump(mode="json"),
    )


async def handle_member_join(
    event: MemberJoinEvent,
    *,
    api_client: Any,
) -> MemberJoinOutcomeRead:
    response = await api_client.call(
        ApiTransportRequest(
            method="GET",
            path=f"/api/v1/members/by-discord/{event.discord_user_id}",
            headers=SERVICE_ACTOR_HEADERS,
        )
    )
    if response.status == 404:
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path="/api/v1/members",
                body=_originating_body(
                    event,
                    discord_user_id=event.discord_user_id,
                    joined_at=event.joined_at.isoformat(),
                ),
                headers=SERVICE_ACTOR_HEADERS,
            ),
            step="member_create",
        )
    elif response.status >= 400:
        raise MemberOnboardingError(
            step="member_lookup",
            status=response.status,
            body=response.body,
        )

    member = response.body or {}
    trust_response = await _api_call(
        api_client,
        ApiTransportRequest(
            method="POST",
            path=f"/api/v1/trust/compute/{member['id']}",
            body=_signals_body(event),
            headers=SERVICE_ACTOR_HEADERS,
        ),
        step="trust_compute",
    )
    trust = trust_response.body or {}
    return MemberJoinOutcomeRead(
        member=member,
        trust=trust,
        intake_required=trust.get("tier") == "low",
    )


__all__ = [
    "MemberOnboardingError",
    "SERVICE_ACTOR_HEADERS",
    "handle_member_join",
]
