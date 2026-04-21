from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportError, ApiTransportRequest, ApiTransportResponse
from app.contracts.interactions import InteractionEnvelope
from app.handlers.application_review import handle_application_approve, handle_application_claim


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
        body={"id": "33333333-3333-4333-8333-333333333333"},
        headers={"etag": '"1"'},
    )


def _application(*, version: int = 2, state: str = "queued") -> dict[str, object]:
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "state": state,
        "version": version,
    }


def _response(status: int, body: dict[str, object], etag: str = '"2"') -> ApiTransportResponse:
    return ApiTransportResponse(status=status, body=body, headers={"etag": etag})


def _envelope(*, ack=None, action: str = "claim") -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-2",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="discord-reviewer-1",
        guild_id="900000000000000001",
        command_name=f"application_{action}",
        arguments={
            "application_id": "22222222-2222-4222-8222-222222222222",
            "decision_reason": "accepted",
        },
        ack_deferred=ack,
    )


@pytest.mark.asyncio
async def test_claim_gets_etag_then_posts_transition_after_ack() -> None:
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApi(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    api = RecordingApi(
        [
            _member_response(),
            _response(200, _application(), '"2"'),
            _response(200, _application(version=3, state="claimed"), '"3"'),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_review_channel=channel)

    result = await handle_application_claim(_envelope(ack=ack), api_client=api, guild=guild)

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    assert [call.method for call in api.calls] == ["GET", "GET", "POST"]
    assert api.calls[2].headers["If-Match"] == '"2"'
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_already_claimed_conflict_posts_no_outcome() -> None:
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(), '"2"'),
            _response(
                409,
                {
                    "code": "application_already_claimed",
                    "owner_id": "other-reviewer",
                    "current_version": 3,
                },
            ),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_review_channel=channel)

    result = await handle_application_claim(_envelope(), api_client=api, guild=guild)

    assert result.success is False
    assert "Application already claimed by other-reviewer." == result.response_text
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_review_posts_retry_notice_no_outcome() -> None:
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(state="in_review"), '"4"'),
            _response(412, {"code": "stale_application_version"}),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_review_channel=channel)

    result = await handle_application_approve(_envelope(action="approve"), api_client=api, guild=guild)

    assert result.success is False
    assert result.response_text == "Application changed. Retry the review action."
    channel.send.assert_not_awaited()
