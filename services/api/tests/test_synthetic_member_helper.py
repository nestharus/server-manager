from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import members as members_service


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        pytest.param(
            SimpleNamespace(
                kind="discord",
                discord_user_id="public:prefix-is-not-the-discriminator",
            ),
            False,
            id="object-kind-discord",
        ),
        pytest.param(
            SimpleNamespace(
                kind="public_intake",
                discord_user_id="9876543210",
            ),
            True,
            id="object-kind-public-intake",
        ),
        pytest.param(
            {
                "kind": "discord",
                "discord_user_id": "public:prefix-is-not-the-discriminator",
            },
            False,
            id="mapping-kind-discord",
        ),
        pytest.param(
            {
                "kind": "public_intake",
                "discord_user_id": "9876543210",
            },
            True,
            id="mapping-kind-public-intake",
        ),
        pytest.param(
            SimpleNamespace(discord_user_id="public:missing-kind"),
            False,
            id="object-without-kind-defensive-default",
        ),
        pytest.param(
            "public:raw-string-is-not-supported",
            False,
            id="raw-string-no-prefix-overload",
        ),
    ],
)
def test_is_synthetic_member_uses_kind_discriminator(
    candidate: object,
    expected: bool,
) -> None:
    """Risk annotation: group=TG-2; named_risk=helper_prefix_discriminator_drift;
    level=unit; source=.tmp/init-125a/phase6/step6a-contract.md#C3 and
    planning/proposals/06-members-kind.md#Helper-unit.
    """

    assert members_service.is_synthetic_member(candidate) is expected
