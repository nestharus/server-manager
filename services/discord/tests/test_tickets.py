from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
)
from app.contracts.interactions import InteractionEnvelope
from app.commands.tickets import (
    TICKET_OPEN_COMMAND,
    TICKET_TRANSITION_COMMAND,
    register_ticket_commands,
)
from app.handlers.tickets import (
    SERVICE_ACTOR_HEADERS,
    _ticket_channel_name,
    build_user_actor_headers,
    handle_ticket_open,
    handle_ticket_transition,
)


class FakeApiClient:
    def __init__(self, responses: list[ApiTransportResponse] | None = None) -> None:
        self.responses = list(responses or [])
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


class ErroringTransitionApi(FakeApiClient):
    def __init__(self, *, error_status: int, error_body: dict[str, Any]) -> None:
        super().__init__(
            [
                ApiTransportResponse(
                    status=200,
                    body=_ticket_read(version=1),
                    headers={"etag": '"1"'},
                )
            ]
        )
        self._error_status = error_status
        self._error_body = error_body

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        self.calls.append(request)
        if len(self.calls) == 1:
            return self.responses.pop(0)
        raise ApiTransportError(
            status=self._error_status,
            body=self._error_body,
            reason=f"API returned status {self._error_status}",
        )


class MockChannel:
    def __init__(self, *, name: str, channel_id: str = "chan-1") -> None:
        self.id = channel_id
        self.name = name
        self.topic: str | None = None
        self.send = AsyncMock()


class MockGuild:
    def __init__(self) -> None:
        self.channels: list[Any] = []
        self.threads: list[Any] = []
        self.create_text_channel = AsyncMock(side_effect=self._create_text_channel)

    async def _create_text_channel(self, name: str, *, topic: str | None = None) -> Any:
        channel = MockChannel(name=name, channel_id=f"chan-{len(self.channels) + 1}")
        channel.topic = topic
        self.channels.append(channel)
        return channel


class FetchingBot:
    def __init__(self, *, api_client: FakeApiClient, guild: MockGuild) -> None:
        self.api_client = api_client
        self.guild = guild
        self.fetch_guild_ids: list[int] = []
        self.handlers: dict[str, Any] = {}

    def get_guild(self, guild_id: int) -> Any | None:
        return None

    async def fetch_guild(self, guild_id: int) -> Any:
        self.fetch_guild_ids.append(guild_id)
        return self.guild

    def register_interaction_handler(self, name: str, handler: Any) -> None:
        self.handlers[name] = handler


def _ticket_read(*, version: int) -> dict[str, Any]:
    ticket_id = "11111111-1111-4111-8111-111111111111"
    return {
        "id": ticket_id,
        "category_id": "22222222-2222-4222-8222-222222222222",
        "category_version": 1,
        "category_snapshot": {
            "schema_version": 1,
            "category_id": "22222222-2222-4222-8222-222222222222",
            "name": "Appeal",
            "category_version": 1,
            "routing_scope": {
                "scope_kind": "chapter",
                "scope_id": "chapter-1",
                "queue": "officers",
            },
            "privacy_level": "reporter_staff",
            "state_machine": {
                "schema_version": 1,
                "initial_state": "open",
                "states": [
                    {"key": "open", "label": "Open", "terminal": False},
                    {"key": "closed", "label": "Closed", "terminal": True},
                ],
                "edges": [],
            },
            "sla_rules": {"schema_version": 1, "rules": []},
        },
        "reporter_id": "reporter-1",
        "subject_id": None,
        "state": "open" if version == 1 else "closed",
        "priority": "normal",
        "owner_id": None,
        "resolution": None,
        "terminal_at": None,
        "created_at": "2026-04-21T00:00:00Z",
        "updated_at": "2026-04-21T00:00:00Z",
        "version": version,
    }


def _open_response(*, status: int = 201) -> ApiTransportResponse:
    body = {
        "ticket": _ticket_read(version=1),
        "initial_message": {
            "id": "33333333-3333-4333-8333-333333333333",
            "ticket_id": "11111111-1111-4111-8111-111111111111",
            "message_seq": 1,
            "author_actor_kind": "user",
            "author_actor_id": "reporter-1",
            "visibility": "reporter_visible",
            "body_markdown": "Open ticket",
            "client_message_id": "interaction-1",
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "created_at": "2026-04-21T00:00:00Z",
        },
    }
    if status == 409:
        body = {"code": "duplicate_ticket_create", **body}
    return ApiTransportResponse(
        status=status,
        body=body,
        headers={"etag": '"1"'},
    )


def _open_envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="reporter-1",
        guild_id="900000000000000001",
        command_name="ticket_open",
        arguments={
            "category_id": "22222222-2222-4222-8222-222222222222",
            "message": "Open ticket",
        },
        ack_deferred=ack,
    )


def _transition_envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-2",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="moderator-1",
        guild_id="900000000000000001",
        command_name="ticket_transition",
        arguments={
            "ticket_id": "11111111-1111-4111-8111-111111111111",
            "action": "close",
            "to_state": "closed",
            "reason": "done",
            "resolution": "resolved",
        },
        ack_deferred=ack,
    )


@pytest.mark.asyncio
async def test_api_500_creates_no_discord_state() -> None:
    # AC4, D14
    guild = MockGuild()
    api = FakeApiClient([ApiTransportResponse(status=500, body={"detail": "boom"}, headers={})])

    result = await handle_ticket_open(_open_envelope(), api_client=api, guild=guild)

    assert result.success is False
    guild.create_text_channel.assert_not_awaited()
    assert guild.channels == []


@pytest.mark.asyncio
async def test_registered_ticket_commands_fetch_guild_on_cache_miss() -> None:
    guild = MockGuild()
    api = FakeApiClient(
        [
            _open_response(status=201),
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=1),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=2),
                headers={"etag": '"2"'},
            ),
        ]
    )
    bot = FetchingBot(api_client=api, guild=guild)
    register_ticket_commands(bot)

    open_result = await bot.handlers[TICKET_OPEN_COMMAND](_open_envelope())
    transition_result = await bot.handlers[TICKET_TRANSITION_COMMAND](
        _transition_envelope()
    )

    assert open_result.success is True
    assert transition_result.success is True
    assert bot.fetch_guild_ids == [900000000000000001, 900000000000000001]


@pytest.mark.asyncio
async def test_api_201_then_discord_create() -> None:
    # AC4, D14
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApiClient(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    guild = MockGuild()
    api = RecordingApiClient([_open_response(status=201)])

    result = await handle_ticket_open(_open_envelope(ack=ack), api_client=api, guild=guild)

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    assert guild.create_text_channel.await_count == 1
    created_channel = guild.channels[0]
    assert created_channel.name == _ticket_channel_name(
        UUID("11111111-1111-4111-8111-111111111111")
    )
    assert created_channel.topic == "ticket_id=11111111-1111-4111-8111-111111111111"
    created_channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_409_duplicate_rediscovers_without_second_ticket() -> None:
    # AC4, D13, D14
    guild = MockGuild()
    existing_name = _ticket_channel_name(UUID("11111111-1111-4111-8111-111111111111"))
    guild.channels.append(MockChannel(name=existing_name))
    api = FakeApiClient([_open_response(status=409)])

    result = await handle_ticket_open(_open_envelope(), api_client=api, guild=guild)

    assert result.success is True
    guild.create_text_channel.assert_not_awaited()
    assert len(guild.channels) == 1


@pytest.mark.asyncio
async def test_service_actor_headers_set() -> None:
    # AC4, D14
    guild = MockGuild()
    api = FakeApiClient([_open_response(status=201)])

    await handle_ticket_open(_open_envelope(), api_client=api, guild=guild)

    call = api.calls[0]
    assert call.headers == SERVICE_ACTOR_HEADERS
    assert call.body["client_ticket_id"] == "interaction-1"
    assert call.body["initial_message"]["client_message_id"] == "interaction-1"


@pytest.mark.asyncio
async def test_transition_command_passes_if_match_header() -> None:
    # AC4, D14
    guild = MockGuild()
    channel = MockChannel(name=_ticket_channel_name(UUID("11111111-1111-4111-8111-111111111111")))
    guild.channels.append(channel)
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=1),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=2),
                headers={"etag": '"2"'},
            ),
        ]
    )

    result = await handle_ticket_transition(
        _transition_envelope(),
        api_client=api,
        guild=guild,
    )

    assert result.success is True
    assert api.calls[0].method == "GET"
    assert api.calls[1].headers["If-Match"] == '"1"'


@pytest.mark.asyncio
async def test_transition_command_stale_version_returns_ephemeral_error() -> None:
    # AC4, D14
    api = ErroringTransitionApi(
        error_status=412,
        error_body={"code": "stale_ticket_version", "message": "stale"},
    )

    result = await handle_ticket_transition(_transition_envelope(), api_client=api, guild=MockGuild())

    assert result.success is False
    assert result.ephemeral is True
    assert "Retry" in (result.response_text or "")


@pytest.mark.asyncio
async def test_transition_command_missing_reason_returns_ephemeral_error() -> None:
    # AC4, D14
    api = ErroringTransitionApi(
        error_status=409,
        error_body={
            "code": "ticket_transition_reason_required",
            "message": "reason required",
        },
    )

    result = await handle_ticket_transition(_transition_envelope(), api_client=api, guild=MockGuild())

    assert result.success is False
    assert result.ephemeral is True
    assert result.response_text == "reason required"


@pytest.mark.asyncio
async def test_transition_command_succeeds_posts_summary_message() -> None:
    # AC4, D14
    guild = MockGuild()
    channel = MockChannel(name=_ticket_channel_name(UUID("11111111-1111-4111-8111-111111111111")))
    guild.channels.append(channel)
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=1),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=2),
                headers={"etag": '"2"'},
            ),
        ]
    )

    result = await handle_ticket_transition(_transition_envelope(), api_client=api, guild=guild)

    assert result.success is True
    channel.send.assert_awaited_once()
    assert "transitioned" in channel.send.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_transition_command_uses_user_actor_not_service_actor() -> None:
    # AC4, D14
    guild = MockGuild()
    channel = MockChannel(name=_ticket_channel_name(UUID("11111111-1111-4111-8111-111111111111")))
    guild.channels.append(channel)
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=1),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body=_ticket_read(version=2),
                headers={"etag": '"2"'},
            ),
        ]
    )

    await handle_ticket_transition(_transition_envelope(), api_client=api, guild=guild)

    assert api.calls[0].headers == build_user_actor_headers("moderator-1")
    assert api.calls[1].headers["X-Actor-Kind"] == "user"
    assert api.calls[1].headers["X-Actor-Id"] == "moderator-1"
