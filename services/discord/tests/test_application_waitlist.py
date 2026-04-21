from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportError, ApiTransportRequest, ApiTransportResponse
from app.contracts.interactions import InteractionEnvelope
from app.handlers.application_waitlist import (
    handle_application_reactivate,
    handle_application_waitlist,
)


APPLICATION_ID = "22222222-2222-4222-8222-222222222222"
MEMBER_ID = "33333333-3333-4333-8333-333333333333"
NEW_OWNER_ID = "44444444-4444-4444-8444-444444444444"


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
        body={"id": MEMBER_ID},
        headers={"etag": '"1"'},
    )


def _application(*, version: int = 4, state: str = "in_review") -> dict[str, object]:
    return {
        "id": APPLICATION_ID,
        "state": state,
        "version": version,
        "interview_thread_id": None,
    }


def _response(status: int, body: dict[str, object], etag: str = '"4"') -> ApiTransportResponse:
    return ApiTransportResponse(status=status, body=body, headers={"etag": etag})


def _waitlist_envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-4",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="discord-reviewer-1",
        guild_id="900000000000000001",
        command_name="application_waitlist",
        arguments={"application_id": APPLICATION_ID, "reason": "waiting on time"},
        ack_deferred=ack,
    )


def _reactivate_envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-5",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="discord-reviewer-1",
        guild_id="900000000000000001",
        command_name="application_reactivate",
        arguments={
            "application_id": APPLICATION_ID,
            "new_owner_id": NEW_OWNER_ID,
            "reason": "ready again",
        },
        ack_deferred=ack,
    )


@pytest.mark.asyncio
async def test_waitlist_defers_gets_etag_posts_then_sends_one_status() -> None:
    """AC4: waitlist sends applicant status only after API success."""
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
            _response(200, _application(), '"4"'),
            _response(200, _application(version=5, state="waitlisted"), '"5"'),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_status_channel=channel)

    result = await handle_application_waitlist(
        _waitlist_envelope(ack=ack),
        api_client=api,
        guild=guild,
    )

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    assert [call.method for call in api.calls] == ["GET", "GET", "POST"]
    assert api.calls[2].path == f"/api/v1/applications/{APPLICATION_ID}/waitlist"
    assert api.calls[2].headers["If-Match"] == '"4"'
    assert api.calls[2].body == {
        "reason": "waiting on time",
        "originating_actor_kind": "user",
        "originating_actor_id": MEMBER_ID,
    }
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [409, 412, 422, 500])
async def test_waitlist_failures_send_no_applicant_status(status: int) -> None:
    """AC4: waitlist conflict, stale, validation, and transport failures stay ephemeral."""
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(), '"4"'),
            _response(status, {"code": "error"}),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_status_channel=channel)

    result = await handle_application_waitlist(_waitlist_envelope(), api_client=api, guild=guild)

    assert result.success is False
    assert result.ephemeral is True
    channel.send.assert_not_awaited()

@pytest.mark.asyncio
async def test_reactivate_gets_etag_and_posts_with_if_match() -> None:
    """AC2: reactivate POST uses current ETag and returns claimed."""
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(version=5, state="waitlisted"), '"5"'),
            _response(200, _application(version=6, state="claimed"), '"6"'),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_status_channel=channel)

    result = await handle_application_reactivate(
        _reactivate_envelope(),
        api_client=api,
        guild=guild,
    )

    assert result.success is True
    assert [call.method for call in api.calls] == ["GET", "GET", "POST"]
    assert api.calls[2].path == f"/api/v1/applications/{APPLICATION_ID}/reactivate"
    assert api.calls[2].headers["If-Match"] == '"5"'
    assert api.calls[2].body == {
        "new_owner_id": NEW_OWNER_ID,
        "reason": "ready again",
        "originating_actor_kind": "user",
        "originating_actor_id": MEMBER_ID,
    }
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [409, 412, 422, 500])
async def test_reactivate_failures_send_no_visible_status(status: int) -> None:
    """AC4: reactivate failures do not send visible status messages."""
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(version=5, state="waitlisted"), '"5"'),
            _response(status, {"code": "error"}),
        ]
    )
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(application_status_channel=channel)

    result = await handle_application_reactivate(_reactivate_envelope(), api_client=api, guild=guild)

    assert result.success is False
    assert result.ephemeral is True
    channel.send.assert_not_awaited()
