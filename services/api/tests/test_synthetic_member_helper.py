from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import members as members_service


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        pytest.param(
            "public:abc123",
            True,
            id="raw-public-prefix",
        ),
        pytest.param(
            "9876543210",
            False,
            id="raw-numeric-discord-id",
        ),
        pytest.param(
            SimpleNamespace(discord_user_id="public:member-object"),
            True,
            id="member-like-public-prefix",
        ),
        pytest.param(
            SimpleNamespace(discord_user_id="9876543210"),
            False,
            id="member-like-numeric-discord-id",
        ),
        pytest.param(
            "",
            False,
            id="empty-string",
        ),
        pytest.param(
            None,
            False,
            id="none",
        ),
    ],
)
def test_is_synthetic_member_identifies_only_public_prefix(
    candidate: object,
    expected: bool,
) -> None:
    """Risk annotation: group=TG-1; named_risk=synthetic_predicate_drift;
    level=unit; source=.tmp/init-124/phase6/step6a-contract.md#C1 and
    proposals/05-synthetic-member-guard.md#Assumption-register-A1.
    """

    assert members_service.is_synthetic_member(candidate) is expected
