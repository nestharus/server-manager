from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportError, ApiTransportRequest, ApiTransportResponse
from app.contracts.interactions import InteractionEnvelope
from app.handlers.application_interview import (
    _interview_thread_name,
    handle_application_interview,
)


APPLICATION_ID = "22222222-2222-4222-8222-222222222222"
MEMBER_ID = "33333333-3333-4333-8333-333333333333"


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


class MockThread:
    def __init__(self, *, thread_id: str, name: str) -> None:
        self.id = thread_id
        self.name = name
        self.topic: str | None = None
        self.application_marker: str | None = None
        self.send = AsyncMock()


class MockReviewChannel:
    def __init__(self) -> None:
        self.threads: list[MockThread] = []
        self.create_thread = AsyncMock(side_effect=self._create_thread)

    async def _create_thread(self, *, name: str, reason: str | None = None) -> MockThread:
        thread = MockThread(thread_id=f"thread-{len(self.threads) + 1}", name=name)
        thread.topic = reason
        thread.application_marker = reason
        self.threads.append(thread)
        return thread


class MockGuild:
    def __init__(self) -> None:
        self.application_review_channel = MockReviewChannel()

    @property
    def threads(self) -> list[MockThread]:
        return self.application_review_channel.threads


def _member_response() -> ApiTransportResponse:
    return ApiTransportResponse(
        status=200,
        body={"id": MEMBER_ID},
        headers={"etag": '"1"'},
    )


def _application(
    *,
    version: int = 4,
    state: str = "in_review",
    interview_thread_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": APPLICATION_ID,
        "state": state,
        "version": version,
        "interview_thread_id": interview_thread_id,
    }


def _response(status: int, body: dict[str, object], etag: str = '"4"') -> ApiTransportResponse:
    return ApiTransportResponse(status=status, body=body, headers={"etag": etag})


def _envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-3",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="discord-reviewer-1",
        guild_id="900000000000000001",
        command_name="application_interview",
        arguments={"application_id": APPLICATION_ID, "reason": "voice check"},
        ack_deferred=ack,
    )


@pytest.mark.asyncio
async def test_interview_defers_gets_application_creates_thread_then_posts() -> None:
    """AC3: interview command creates one deterministic thread before POST."""
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApi(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    guild = MockGuild()
    api = RecordingApi(
        [
            _member_response(),
            _response(200, _application(), '"4"'),
            _response(200, _application(version=5, state="interview", interview_thread_id="thread-1"), '"5"'),
        ]
    )

    result = await handle_application_interview(_envelope(ack=ack), api_client=api, guild=guild)

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    assert [call.method for call in api.calls] == ["GET", "GET", "POST"]
    assert api.calls[2].path == f"/api/v1/applications/{APPLICATION_ID}/interview"
    assert api.calls[2].headers["If-Match"] == '"4"'
    assert api.calls[2].body["thread_id"] == "thread-1"
    assert api.calls[2].body["originating_actor_id"] == MEMBER_ID
    guild.application_review_channel.create_thread.assert_awaited_once()
    assert guild.threads[0].name == _interview_thread_name(APPLICATION_ID)


@pytest.mark.asyncio
async def test_interview_existing_thread_id_is_reused_without_creation() -> None:
    """AC3: existing interview_thread_id from GET is reused."""
    guild = MockGuild()
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(state="interview", interview_thread_id="thread-known"), '"5"'),
            _response(200, _application(version=5, state="interview", interview_thread_id="thread-known"), '"5"'),
        ]
    )

    result = await handle_application_interview(_envelope(), api_client=api, guild=guild)

    assert result.success is True
    assert api.calls[2].body["thread_id"] == "thread-known"
    guild.application_review_channel.create_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_interview_conflicts_return_ephemeral_error_without_success_message() -> None:
    """AC4: interview API conflict sends no success outcome."""
    guild = MockGuild()
    api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(state="interview", interview_thread_id="thread-known"), '"5"'),
            _response(
                409,
                {
                    "code": "application_interview_thread_mismatch",
                    "current_thread_id": "thread-known",
                    "requested_thread_id": "thread-other",
                },
            ),
        ]
    )

    result = await handle_application_interview(_envelope(), api_client=api, guild=guild)

    assert result.success is False
    assert result.ephemeral is True
    assert "different interview thread" in (result.response_text or "")
    guild.application_review_channel.create_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_interview_retry_discovers_marker_before_creating_duplicate() -> None:
    """AC4: retry discovers deterministic thread name before creating another."""
    guild = MockGuild()
    first_api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(), '"4"'),
            _response(412, {"code": "stale_application_version"}),
        ]
    )
    first = await handle_application_interview(_envelope(), api_client=first_api, guild=guild)
    assert first.success is False
    assert guild.application_review_channel.create_thread.await_count == 1

    second_api = FakeApiClient(
        [
            _member_response(),
            _response(200, _application(), '"4"'),
            _response(200, _application(version=5, state="interview", interview_thread_id="thread-1"), '"5"'),
        ]
    )
    second = await handle_application_interview(_envelope(), api_client=second_api, guild=guild)

    assert second.success is True
    assert second_api.calls[2].body["thread_id"] == "thread-1"
    assert guild.application_review_channel.create_thread.await_count == 1
    assert len(guild.threads) == 1
