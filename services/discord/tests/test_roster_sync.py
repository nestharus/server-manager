from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import discord
import pytest

from app.contracts.api_transport import ApiTransportRequest, ApiTransportResponse
from app.contracts.roster import RosterSyncEvent
from app.handlers.roster import SERVICE_ACTOR_HEADERS, sync_roster


TRANSITION_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeApiClient:
    def __init__(self, responses: list[ApiTransportResponse]) -> None:
        self.responses = responses
        self.calls: list[ApiTransportRequest] = []

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        self.calls.append(request)
        return self.responses.pop(0)


class FakeMember:
    def __init__(self, *, roles: list[Any] | None = None, fail: Exception | None = None) -> None:
        self.id = "1234"
        self.roles = list(roles or [])
        self._fail = fail
        self.add_roles = AsyncMock(side_effect=self._add_roles)
        self.remove_roles = AsyncMock(side_effect=self._remove_roles)

    async def _add_roles(
        self,
        *roles: Any,
        reason: str | None = None,
        atomic: bool = True,
    ) -> None:
        if self._fail is not None:
            raise self._fail
        self.roles.extend(roles)

    async def _remove_roles(
        self,
        *roles: Any,
        reason: str | None = None,
        atomic: bool = True,
    ) -> None:
        if self._fail is not None:
            raise self._fail
        for role in roles:
            if role in self.roles:
                self.roles.remove(role)


class FakeGuild:
    def __init__(self, *, member: FakeMember | None, roles: list[Any]) -> None:
        self.members = [] if member is None else [member]
        self.roles = roles
        self.fetch_member = AsyncMock(side_effect=discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "missing"))

    def get_member(self, user_id: int) -> FakeMember | None:
        for member in self.members:
            if str(member.id) == str(user_id):
                return member
        return None


def _role(role_id: str, name: str) -> Any:
    return SimpleNamespace(id=role_id, name=name)


def _event(**overrides: Any) -> RosterSyncEvent:
    payload: dict[str, Any] = {
        "roster_entry_id": "entry-1",
        "roster_entry_version": 2,
        "transition_id": str(TRANSITION_ID),
        "chapter_id": "ch-1",
        "member_id": "member-1",
        "member_discord_user_id": "1234",
        "chapter_role_name": "member",
        "chapter_discord_role_id": None,
        "chapter_discord_resources": {"role_ids": {"member": "role-1"}},
        "status": "active",
        "originating_actor_kind": "user",
        "originating_actor_id": "1001",
        "reason": "operator requested",
    }
    payload.update(overrides)
    return RosterSyncEvent.model_validate(payload)


def _response(status: int = 200) -> ApiTransportResponse:
    return ApiTransportResponse(status=status, body={"ok": True}, headers={"etag": '"3"'})


@pytest.mark.asyncio
async def test_discord_handler_calls_sync_failure_on_forbidden() -> None:
    forbidden = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "denied")
    role = _role("role-1", "member")
    member = FakeMember(fail=forbidden)
    guild = FakeGuild(member=member, roles=[role])
    api = FakeApiClient([_response()])

    result = await sync_roster(_event(), api_client=api, guild=guild)

    assert result.failure_recorded is True
    assert result.applied_role_ids == []
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call.method == "POST"
    assert call.path == "/api/v1/roster-entries/entry-1/sync-failure"
    assert call.headers == {**SERVICE_ACTOR_HEADERS, "If-Match": '"2"'}
    assert call.body["transition_id"] == str(TRANSITION_ID)
    assert call.body["operation"] == "add_roles"
    assert call.body["desired_discord_role_ids"] == ["role-1"]
    assert call.body["error_type"] == "Forbidden"


@pytest.mark.asyncio
async def test_discord_handler_rediscovers_role_id_by_name() -> None:
    stale_role = _role("role-stale", "stale")
    rediscovered = _role("role-2", "member")
    member = FakeMember()
    guild = FakeGuild(member=member, roles=[stale_role, rediscovered])
    api = FakeApiClient([])

    result = await sync_roster(
        _event(chapter_discord_role_id="role-stale"),
        api_client=api,
        guild=guild,
    )

    assert result.applied_role_ids == ["role-2"]
    assert result.failure_recorded is False
    member.add_roles.assert_awaited_once()
    roles_arg = member.add_roles.await_args.args[0]
    assert roles_arg == rediscovered
    assert api.calls == []


@pytest.mark.asyncio
async def test_discord_handler_acks_deferred_before_api_calls() -> None:
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    class RecordingApiClient(FakeApiClient):
        async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
            events.append("api")
            return await super().call(request)

    forbidden = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "denied")
    role = _role("role-1", "member")
    member = FakeMember(fail=forbidden)
    guild = FakeGuild(member=member, roles=[role])
    api = RecordingApiClient([_response()])

    await sync_roster(_event(ack_deferred=ack), api_client=api, guild=guild)

    assert events[:2] == ["ack", "api"]
