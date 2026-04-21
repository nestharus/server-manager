from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.contracts.api_transport import ApiTransportRequest, ApiTransportResponse
from app.contracts.onboarding import MemberJoinEvent, MemberJoinOutcomeRead


SERVICE_HEADERS = {
    "X-Actor-Kind": "service",
    "X-Actor-Id": "member-onboarder",
}


class FakeApiClient:
    def __init__(self, responses: list[ApiTransportResponse]) -> None:
        self.responses = responses
        self.calls: list[ApiTransportRequest] = []

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        self.calls.append(request)
        return self.responses.pop(0)


def _event(
    *,
    discord_user_id: str = "1234",
    actor_id: str = "1001",
    joined_at: datetime | None = None,
) -> MemberJoinEvent:
    return MemberJoinEvent.model_validate(
        {
            "discord_user_id": discord_user_id,
            "joined_at": (joined_at or datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)).isoformat(),
            "signals": {
                "discord_account_age_days": 14,
                "has_avatar": True,
                "has_verified_badge": False,
                "account_flags": [],
            },
            "originating_actor_id": actor_id,
        }
    )


def _member_body(
    *,
    member_id: str,
    discord_user_id: str,
    joined_at: datetime,
    status: str = "active",
    version: int = 1,
) -> dict[str, Any]:
    return {
        "id": member_id,
        "discord_user_id": discord_user_id,
        "joined_at": joined_at.isoformat(),
        "status": status,
        "created_at": joined_at.isoformat(),
        "updated_at": joined_at.isoformat(),
        "version": version,
    }


def _trust_body(
    *,
    member_id: str,
    score: int = 42,
    tier: str = "low",
    policy_version_id: str | None = None,
    signals: dict[str, Any] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    return {
        "member_id": member_id,
        "score": score,
        "tier": tier,
        "signals": signals
        or {
            "discord_account_age_days": 14,
            "has_avatar": True,
            "has_verified_badge": False,
            "account_flags": [],
        },
        "policy_version_id": policy_version_id or str(uuid4()),
        "version": version,
    }


@pytest.mark.asyncio
async def test_handle_member_join_creates_member_when_absent() -> None:
    member_id = str(uuid4())
    event = _event()
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=404,
                body={"code": "member_not_found"},
                headers={},
            ),
            ApiTransportResponse(
                status=201,
                body=_member_body(
                    member_id=member_id,
                    discord_user_id=event.discord_user_id,
                    joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=201,
                body=_trust_body(
                    member_id=member_id,
                    tier="low",
                    policy_version_id=str(uuid4()),
                ),
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import handle_member_join

    outcome = await handle_member_join(event, api_client=api)

    assert isinstance(outcome, MemberJoinOutcomeRead)
    assert outcome.intake_required is True
    assert outcome.member["id"] == member_id
    assert outcome.trust["member_id"] == member_id
    assert [call.method for call in api.calls] == ["GET", "POST", "POST"]
    assert api.calls[0].path == f"/api/v1/members/by-discord/{event.discord_user_id}"
    assert api.calls[0].headers == SERVICE_HEADERS
    assert api.calls[1].path == "/api/v1/members"
    assert api.calls[1].headers == SERVICE_HEADERS
    assert api.calls[1].body == {
        "discord_user_id": event.discord_user_id,
        "joined_at": event.joined_at.isoformat(),
        "originating_actor_kind": "user",
        "originating_actor_id": event.originating_actor_id,
    }
    assert api.calls[2].path == f"/api/v1/trust/compute/{member_id}"
    assert api.calls[2].headers == SERVICE_HEADERS
    assert api.calls[2].body == {
        "discord_account_age_days": 14,
        "has_avatar": True,
        "has_verified_badge": False,
        "account_flags": [],
        "originating_actor_kind": "user",
        "originating_actor_id": event.originating_actor_id,
    }


@pytest.mark.asyncio
async def test_handle_member_join_reuses_member_when_present() -> None:
    member_id = str(uuid4())
    event = _event()
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_member_body(
                    member_id=member_id,
                    discord_user_id=event.discord_user_id,
                    joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body=_trust_body(
                    member_id=member_id,
                    tier="high",
                    policy_version_id=str(uuid4()),
                ),
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import handle_member_join

    outcome = await handle_member_join(event, api_client=api)

    assert isinstance(outcome, MemberJoinOutcomeRead)
    assert outcome.intake_required is False
    assert outcome.member["id"] == member_id
    assert outcome.trust["tier"] == "high"
    assert [call.method for call in api.calls] == ["GET", "POST"]
    assert api.calls[0].path == f"/api/v1/members/by-discord/{event.discord_user_id}"
    assert api.calls[1].path == f"/api/v1/trust/compute/{member_id}"
    assert api.calls[1].body["originating_actor_id"] == event.originating_actor_id


@pytest.mark.asyncio
async def test_handle_member_join_computes_trust_and_derives_intake_required() -> None:
    member_id = str(uuid4())
    event = _event()
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_member_body(
                    member_id=member_id,
                    discord_user_id=event.discord_user_id,
                    joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=201,
                body=_trust_body(
                    member_id=member_id,
                    tier="low",
                    policy_version_id=str(uuid4()),
                ),
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import handle_member_join

    outcome = await handle_member_join(event, api_client=api)

    assert outcome.intake_required is True
    assert outcome.trust["tier"] == "low"
    assert api.calls[1].path == f"/api/v1/trust/compute/{member_id}"
    assert api.calls[1].body["discord_account_age_days"] == 14
    assert api.calls[1].body["has_avatar"] is True


@pytest.mark.asyncio
async def test_handle_member_join_records_originating_user_in_audit() -> None:
    member_id = str(uuid4())
    event = _event(actor_id="9999")
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=404,
                body={"code": "member_not_found"},
                headers={},
            ),
            ApiTransportResponse(
                status=201,
                body=_member_body(
                    member_id=member_id,
                    discord_user_id=event.discord_user_id,
                    joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=201,
                body=_trust_body(member_id=member_id, tier="low"),
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import handle_member_join

    outcome = await handle_member_join(event, api_client=api)

    assert outcome.member["discord_user_id"] == event.discord_user_id
    assert api.calls[1].body["originating_actor_id"] == "9999"
    assert api.calls[2].body["originating_actor_id"] == "9999"


@pytest.mark.asyncio
async def test_handle_member_join_raises_on_malformed_api_response() -> None:
    event = _event()
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body={"discord_user_id": event.discord_user_id},
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import MemberOnboardingError, handle_member_join

    with pytest.raises(MemberOnboardingError) as exc_info:
        await handle_member_join(event, api_client=api)

    assert exc_info.value.step == "member_lookup"
    assert exc_info.value.status == 200
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_handle_member_join_raises_on_malformed_trust_api_response() -> None:
    member_id = str(uuid4())
    event = _event()
    api = FakeApiClient(
        [
            ApiTransportResponse(
                status=200,
                body=_member_body(
                    member_id=member_id,
                    discord_user_id=event.discord_user_id,
                    joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
                headers={"etag": '"1"'},
            ),
            ApiTransportResponse(
                status=200,
                body={
                    "member_id": member_id,
                    "score": 42,
                    "signals": {},
                    "policy_version_id": str(uuid4()),
                    "version": 1,
                },
                headers={"etag": '"1"'},
            ),
        ]
    )

    from app.handlers.onboarding import MemberOnboardingError, handle_member_join

    with pytest.raises(MemberOnboardingError) as exc_info:
        await handle_member_join(event, api_client=api)

    assert exc_info.value.step == "trust_compute"
    assert exc_info.value.status == 200
    assert [call.method for call in api.calls] == ["GET", "POST"]
