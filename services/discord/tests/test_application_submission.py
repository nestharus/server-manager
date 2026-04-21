from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportError, ApiTransportRequest, ApiTransportResponse
from app.contracts.interactions import InteractionEnvelope
from app.handlers.application_submission import handle_application_submit


class FakeApiClient:
    def __init__(self, responses: list[ApiTransportResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[ApiTransportRequest] = []

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        self.calls.append(request)
        response = self.responses.pop(0)
        if response.status >= 500:
            raise ApiTransportError(
                status=response.status,
                body=response.body,
                reason=f"API returned status {response.status}",
            )
        return response


def _member_response() -> ApiTransportResponse:
    return ApiTransportResponse(
        status=200,
        body={"id": "11111111-1111-4111-8111-111111111111"},
        headers={"etag": '"1"'},
    )


def _application_response(*, status: int = 201) -> ApiTransportResponse:
    body: dict[str, Any] = {
        "id": "22222222-2222-4222-8222-222222222222",
        "state": "queued",
        "version": 2,
    }
    if status == 409:
        body = {"code": "duplicate_application_create", "application": body}
    return ApiTransportResponse(status=status, body=body, headers={"etag": '"2"'})


def _envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="discord-user-1",
        guild_id="900000000000000001",
        command_name="application_submit",
        arguments={
            "scope_kind": "chapter",
            "scope_id": "chapter-1",
            "responses": {"nickname": "Ada"},
        },
        ack_deferred=ack,
    )


@pytest.mark.asyncio
async def test_submission_acks_before_api_and_uses_member_actor_headers() -> None:
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApi(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    api = RecordingApi([_member_response(), _application_response()])

    result = await handle_application_submit(_envelope(ack=ack), api_client=api)

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    submit_call = api.calls[1]
    assert submit_call.path == "/api/v1/applications"
    assert submit_call.body["client_application_id"] == "interaction-1"
    assert submit_call.body["applicant_id"] == "11111111-1111-4111-8111-111111111111"
    assert submit_call.headers == {
        "X-Actor-Kind": "user",
        "X-Actor-Id": "11111111-1111-4111-8111-111111111111",
    }


@pytest.mark.asyncio
async def test_duplicate_submission_returns_existing_id_without_failure() -> None:
    api = FakeApiClient([_member_response(), _application_response(status=409)])

    result = await handle_application_submit(_envelope(), api_client=api)

    assert result.success is True
    assert "already submitted" in (result.response_text or "")
    assert len(api.calls) == 2


@pytest.mark.asyncio
async def test_submission_api_500_returns_one_failure() -> None:
    api = FakeApiClient(
        [
            _member_response(),
            ApiTransportResponse(status=500, body={"detail": "boom"}, headers={}),
        ]
    )

    result = await handle_application_submit(_envelope(), api_client=api)

    assert result.success is False
    assert result.response_text == "Application submission failed."
