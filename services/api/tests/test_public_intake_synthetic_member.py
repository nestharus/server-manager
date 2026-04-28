from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.repositories.db import PostgresDatabase
from app.services.members import resolve_or_create_public_intake_member

from .public_intake_fixtures import (
    PUBLIC_MEMBER_SALT,
    assert_risk_annotation,
    count_members_by_discord_id,
    create_real_member,
    fetch_member_discord_ids,
)


pytestmark = pytest.mark.asyncio


async def test_public_intake_member_uses_public_digest_namespace(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=synthetic_member_identity_pollution;
    level=component; source=proposals/02-public-application-intake.md#§2 AS-2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="synthetic_member_identity_pollution",
        level="component",
        source="proposals/02-public-application-intake.md#§2",
    )

    member = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=uuid4(),
        channel_salt=PUBLIC_MEMBER_SALT,
    )

    assert re.fullmatch(r"public:[0-9a-f]{32}", member.discord_user_id)
    assert member.status == "active"
    assert count_members_by_discord_id(governance_dsn, member.discord_user_id) == 1


async def test_public_intake_member_resolution_is_idempotent(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=synthetic_member_identity_pollution;
    level=component; source=proposals/02-public-application-intake.md#§2 AS-2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="synthetic_member_identity_pollution",
        level="component",
        source="proposals/02-public-application-intake.md#§2",
    )
    public_submission_id = uuid4()

    first = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=public_submission_id,
        channel_salt=PUBLIC_MEMBER_SALT,
    )
    second = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=public_submission_id,
        channel_salt=PUBLIC_MEMBER_SALT,
    )

    assert second.id == first.id
    assert second.discord_user_id == first.discord_user_id
    assert count_members_by_discord_id(governance_dsn, first.discord_user_id) == 1


async def test_public_intake_member_is_unique_per_public_submission(
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2; named_risk=synthetic_member_identity_pollution;
    level=component; source=proposals/02-public-application-intake.md#§2 AS-2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="synthetic_member_identity_pollution",
        level="component",
        source="proposals/02-public-application-intake.md#§2",
    )

    first = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=uuid4(),
        channel_salt=PUBLIC_MEMBER_SALT,
    )
    second = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=uuid4(),
        channel_salt=PUBLIC_MEMBER_SALT,
    )

    assert second.id != first.id
    assert second.discord_user_id != first.discord_user_id


async def test_public_intake_prefix_does_not_collide_with_real_member_ids(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=synthetic_member_identity_pollution;
    level=component; source=proposals/02-public-application-intake.md#§2 AS-2.
    """
    assert_risk_annotation(
        group="TG-2",
        named_risk="synthetic_member_identity_pollution",
        level="component",
        source="proposals/02-public-application-intake.md#§2",
    )
    create_real_member(governance_db, "123456789012345678")

    synthetic = await resolve_or_create_public_intake_member(
        governance_db,
        public_submission_id=uuid4(),
        channel_salt=PUBLIC_MEMBER_SALT,
    )

    real_ids = [
        discord_user_id
        for discord_user_id in fetch_member_discord_ids(governance_dsn)
        if discord_user_id != synthetic.discord_user_id
    ]
    assert real_ids == ["123456789012345678"]
    assert all(not discord_user_id.startswith("public:") for discord_user_id in real_ids)
