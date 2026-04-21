from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportRequest, ApiTransportResponse
from app.contracts.interactions import InteractionEnvelope
from app.handlers.chapters import derive_resource_names, provision_chapter_handler


class FakeApiClient:
    def __init__(self, responses: list[ApiTransportResponse]) -> None:
        self.responses = responses
        self.calls: list[ApiTransportRequest] = []

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        self.calls.append(request)
        return self.responses.pop(0)


class MockGuild:
    def __init__(self) -> None:
        self.me = SimpleNamespace(
            guild_permissions=SimpleNamespace(
                manage_channels=True,
                manage_roles=True,
                view_channel=True,
            )
        )
        self.categories: list[Any] = []
        self.roles: list[Any] = []
        self.channels: list[Any] = []
        self.create_category = AsyncMock(side_effect=self._create_category)
        self.create_role = AsyncMock(side_effect=self._create_role)
        self.create_text_channel = AsyncMock(side_effect=self._create_channel)

    async def _create_category(self, name: str) -> Any:
        category = SimpleNamespace(id=f"cat-{len(self.categories) + 1}", name=name)
        self.categories.append(category)
        return category

    async def _create_role(self, *, name: str) -> Any:
        role = SimpleNamespace(id=f"role-{len(self.roles) + 1}", name=name)
        self.roles.append(role)
        return role

    async def _create_channel(self, *, name: str, category: Any) -> Any:
        channel = SimpleNamespace(
            id=f"chan-{len(self.channels) + 1}",
            name=name,
            category=category,
        )
        self.channels.append(channel)
        return channel


def _envelope(*, ack=None) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="1001",
        guild_id="900000000000000001",
        command_name="provision_chapter",
        arguments={"chapter_id": "chapter-1"},
        ack_deferred=ack,
    )


def _chapter(*, state: str = "proposed", resources: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": "chapter-1",
        "name": "Humility Seattle",
        "state": state,
        "discord_resources": resources
        or {"category_id": None, "role_ids": {}, "channel_ids": {}},
        "template_snapshot": {
            "role_structure": [
                {"name": "officer", "ordinal": 10, "triggers_succession": True}
            ],
            "channel_structure": [
                {"name": "general", "type": "text"},
            ],
        },
    }


def _response(body: dict[str, Any], etag: str = '"1"', status: int = 200) -> ApiTransportResponse:
    return ApiTransportResponse(status=status, body=body, headers={"etag": etag})


@pytest.mark.asyncio
async def test_discord_handler_acks_deferred_before_api_calls() -> None:
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApiClient(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    chapter = _chapter()
    names = derive_resource_names(chapter)
    active_resources = {
        "category_id": "cat-1",
        "role_ids": {"officer": "role-1"},
        "channel_ids": {"general": "chan-1"},
    }
    api = RecordingApiClient(
        [
            _response(chapter, '"1"'),
            _response({**chapter, "state": "provisioning"}, '"2"'),
            _response({**chapter, "state": "provisioning", "discord_resources": {"category_id": "cat-1", "role_ids": {}, "channel_ids": {}}}, '"3"'),
            _response({**chapter, "state": "provisioning", "discord_resources": {"category_id": "cat-1", "role_ids": {"officer": "role-1"}, "channel_ids": {}}}, '"4"'),
            _response({**chapter, "state": "provisioning", "discord_resources": active_resources}, '"5"'),
            _response({**chapter, "state": "active", "discord_resources": active_resources}, '"6"'),
        ]
    )
    guild = MockGuild()

    result = await provision_chapter_handler(_envelope(ack=ack), api_client=api, guild=guild)

    assert result.success is True
    assert events[:2] == ["ack", "api"]
    assert api.calls[0].headers == {
        "X-Actor-Kind": "service",
        "X-Actor-Id": "discord-provisioner",
    }
    assert api.calls[1].body["originating_actor_id"] == "1001"
    assert guild.roles[0].name == names["roles"]["officer"]


@pytest.mark.asyncio
async def test_discord_handler_rediscovers_role_by_name_after_patch_failure() -> None:
    chapter = _chapter()
    guild = MockGuild()
    first = FakeApiClient(
        [
            _response(chapter, '"1"'),
            _response({**chapter, "state": "provisioning"}, '"2"'),
            _response({**chapter, "state": "provisioning", "discord_resources": {"category_id": "cat-1", "role_ids": {}, "channel_ids": {}}}, '"3"'),
            _response({"detail": "patch failed"}, '"3"', status=500),
            _response({**chapter, "state": "provisioning_failed"}, '"4"'),
        ]
    )

    first_result = await provision_chapter_handler(_envelope(), api_client=first, guild=guild)

    assert first_result.success is False
    assert guild.create_role.await_count == 1

    retry_resources = {"category_id": "cat-1", "role_ids": {}, "channel_ids": {}}
    retry = FakeApiClient(
        [
            _response(_chapter(state="provisioning_failed", resources=retry_resources), '"4"'),
            _response(_chapter(state="provisioning", resources=retry_resources), '"5"'),
            _response(_chapter(state="provisioning", resources=retry_resources), '"6"'),
            _response(_chapter(state="provisioning", resources={"category_id": "cat-1", "role_ids": {"officer": "role-1"}, "channel_ids": {}}), '"7"'),
            _response(_chapter(state="provisioning", resources={"category_id": "cat-1", "role_ids": {"officer": "role-1"}, "channel_ids": {"general": "chan-1"}}), '"8"'),
            _response(_chapter(state="active", resources={"category_id": "cat-1", "role_ids": {"officer": "role-1"}, "channel_ids": {"general": "chan-1"}}), '"9"'),
        ]
    )

    retry_result = await provision_chapter_handler(_envelope(), api_client=retry, guild=guild)

    assert retry_result.success is True
    assert guild.create_role.await_count == 1
