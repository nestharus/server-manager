from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.members import MemberCreate, MemberRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.services.members import MembersService
from app.services.mutations import mutate_entity
from tests._authority_helpers import grant_authority


BASE_URL = "/api/v1/members"


def _actor_headers(
    *,
    actor_id: str = "operator",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _make_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _grant_permissions(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
) -> None:
    with use_audit_context(_make_audit_context()):
        grant_authority(
            db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "root"),
        )


def _member_payload(
    *,
    discord_user_id: str,
    joined_at: datetime,
    originating_actor_id: str,
    originating_actor_kind: str = "user",
) -> dict[str, Any]:
    return {
        "discord_user_id": discord_user_id,
        "joined_at": joined_at.isoformat(),
        "originating_actor_kind": originating_actor_kind,
        "originating_actor_id": originating_actor_id,
    }


def _fetch_member_count(database_url: str, discord_user_id: str) -> int:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM members
            WHERE discord_user_id = %s
            """,
            (discord_user_id,),
        ).fetchone()
    assert row is not None
    return int(row["count"])


def _fetch_member_kind(database_url: str, member_id: str) -> str:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT kind
            FROM members
            WHERE id = %s
            """,
            (member_id,),
        ).fetchone()
    assert row is not None
    return str(row["kind"])


def _fetch_member_row_by_discord_id(
    database_url: str,
    discord_user_id: str,
) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT m.id, m.discord_user_id, m.kind, h.current_seq AS version
            FROM members AS m
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'member'
             AND h.aggregate_id = m.id::text
            WHERE m.discord_user_id = %s
            """,
            (discord_user_id,),
        ).fetchone()
    assert row is not None
    return dict(row)


def _fetch_latest_member_audit(database_url: str) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT actor_kind, actor_id, request_json
            FROM activity_actions
            WHERE aggregate_type = 'member'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    return row


def _members_service(db: PostgresDatabase) -> MembersService:
    return MembersService(
        members_repo=MembersRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def real_discord_member_resolver():
    async def resolve(db: PostgresDatabase, **kwargs: Any) -> MemberRead:
        return await _members_service(db).resolve_or_create_real_discord_member(
            **kwargs,
        )

    return resolve


@pytest.fixture()
def first_real_discord_user_id() -> str:
    return "223456789012345678"


@pytest.fixture()
def concurrent_real_discord_user_id() -> str:
    return "323456789012345678"


@pytest.mark.asyncio
async def test_create_member_returns_active_with_uuid_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    member = MemberRead.model_validate(response.json())
    assert member.discord_user_id == discord_user_id
    assert member.joined_at == joined_at
    assert member.status == "active"
    assert member.kind == "discord"
    assert response.json()["kind"] == "discord"
    assert member.version == 1
    assert response.headers["etag"] == '"1"'


def test_create_or_get_member_external_signature_does_not_accept_kind() -> None:
    """Risk annotation: group=TG-4; named_risk=caller_supplied_kind_escape_hatch;
    level=component; source=.tmp/init-125a/phase6/step6a-contract.md#Anti-scope and
    planning/proposals/06-members-kind.md#Q3.
    """

    parameters = inspect.signature(MembersService.create_or_get_member).parameters

    assert "kind" not in parameters
    assert "_kind" not in parameters


def test_create_or_get_member_sets_discord_kind(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=normal_member_kind_stamping;
    level=component; source=.tmp/init-125a/phase6/step6a-contract.md#C2 and
    planning/proposals/06-members-kind.md#Normal-creation.
    """
    discord_user_id = str(uuid4())
    request = MemberCreate(
        discord_user_id=discord_user_id,
        joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        originating_actor_id="operator",
    )

    service = _members_service(governance_db)
    with use_audit_context(_make_audit_context()):
        member, _result, created = service.create_or_get_member(
            request,
            ActorIdentity(actor_kind="user", actor_id="operator"),
        )

    assert created is True
    assert member.kind == "discord"
    assert _fetch_member_kind(governance_dsn, str(member.id)) == "discord"


@pytest.mark.asyncio
async def test_resolve_or_create_real_discord_member_creates_discord_member(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    real_discord_member_resolver,
    first_real_discord_user_id: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=real_discord_member_not_created;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C4.
    """
    from .public_intake_fixtures import assert_risk_annotation

    assert_risk_annotation(
        group="TG-4",
        named_risk="real_discord_member_not_created",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C4",
    )

    member = await real_discord_member_resolver(
        governance_db,
        discord_user_id=first_real_discord_user_id,
    )

    assert member.discord_user_id == first_real_discord_user_id
    assert member.kind == "discord"
    row = _fetch_member_row_by_discord_id(governance_dsn, first_real_discord_user_id)
    assert row["id"] == member.id
    assert row["kind"] == "discord"
    assert _fetch_member_count(governance_dsn, first_real_discord_user_id) == 1


@pytest.mark.asyncio
async def test_resolve_or_create_real_discord_member_reuses_existing_discord_member(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    real_discord_member_resolver,
    first_real_discord_user_id: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=real_discord_member_duplicate_insert;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C4.
    """
    from .public_intake_fixtures import assert_risk_annotation

    assert_risk_annotation(
        group="TG-4",
        named_risk="real_discord_member_duplicate_insert",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C4",
    )

    first = await real_discord_member_resolver(
        governance_db,
        discord_user_id=first_real_discord_user_id,
    )
    second = await real_discord_member_resolver(
        governance_db,
        discord_user_id=first_real_discord_user_id,
    )

    assert second.id == first.id
    assert second.discord_user_id == first_real_discord_user_id
    assert second.kind == "discord"
    assert _fetch_member_count(governance_dsn, first_real_discord_user_id) == 1


@pytest.mark.asyncio
async def test_resolve_or_create_real_discord_member_concurrent_calls_converge(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    real_discord_member_resolver,
    concurrent_real_discord_user_id: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=real_discord_member_race_duplicate_insert;
    level=component; source=.tmp/init-128/phase6/step6a-contract.md#C4.
    """
    from .public_intake_fixtures import assert_risk_annotation

    assert_risk_annotation(
        group="TG-4",
        named_risk="real_discord_member_race_duplicate_insert",
        level="component",
        source=".tmp/init-128/phase6/step6a-contract.md#C4",
    )

    first, second = await asyncio.gather(
        real_discord_member_resolver(
            governance_db,
            discord_user_id=concurrent_real_discord_user_id,
        ),
        real_discord_member_resolver(
            governance_db,
            discord_user_id=concurrent_real_discord_user_id,
        ),
    )

    assert second.id == first.id
    assert first.kind == "discord"
    assert second.kind == "discord"
    assert _fetch_member_count(governance_dsn, concurrent_real_discord_user_id) == 1


@pytest.mark.asyncio
async def test_create_member_idempotent_on_duplicate_discord_user_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )
    payload = _member_payload(
        discord_user_id=discord_user_id,
        joined_at=joined_at,
        originating_actor_id=actor_id,
    )

    first = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(actor_id=actor_id),
    )
    second = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(actor_id=actor_id),
    )

    assert first.status_code == HTTPStatus.CREATED, first.text
    assert second.status_code == HTTPStatus.OK, second.text
    created = MemberRead.model_validate(first.json())
    duplicate = MemberRead.model_validate(second.json())
    assert duplicate.id == created.id
    assert duplicate.discord_user_id == discord_user_id
    assert duplicate.version == created.version
    assert second.headers["etag"] == first.headers["etag"]
    assert _fetch_member_count(governance_dsn, discord_user_id) == 1


@pytest.mark.asyncio
async def test_create_member_requires_member_write_permission(
    migrated_async_client: AsyncClient,
) -> None:
    response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=str(uuid4()),
            joined_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            originating_actor_id="operator",
        ),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_get_member_by_id_returns_current_state(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.read", "member.write"}),
    )

    created_response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    created = MemberRead.model_validate(created_response.json())

    response = await migrated_async_client.get(
        f"{BASE_URL}/{created.id}",
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    current = MemberRead.model_validate(response.json())
    assert current == created
    assert current.kind == "discord"
    assert response.json()["kind"] == "discord"
    assert response.headers["etag"] == created_response.headers["etag"]


@pytest.mark.asyncio
async def test_get_member_by_discord_id_404_when_absent(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.read"}),
    )

    response = await migrated_async_client.get(
        f"{BASE_URL}/by-discord/{uuid4()}",
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
    assert response.json()["code"] == "member_not_found"


@pytest.mark.asyncio
async def test_patch_member_status_with_current_version_succeeds_and_advances_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-7; named_risk=member_status_real_member_regression;
    level=particular-integration; source=.tmp/init-124/phase6/step6a-contract.md#C7.
    """
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.read", "member.write"}),
    )

    created_response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    created = MemberRead.model_validate(created_response.json())

    response = await migrated_async_client.patch(
        f"{BASE_URL}/{created.id}/status",
        json={
            "status": "suspended",
            "reason": "operator requested",
            "originating_actor_kind": "user",
            "originating_actor_id": actor_id,
        },
        headers={**_actor_headers(actor_id=actor_id), "If-Match": created_response.headers["etag"]},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    patched = MemberRead.model_validate(response.json())
    assert patched.status == "suspended"
    assert patched.version == 2
    assert response.headers["etag"] == '"2"'


@pytest.mark.asyncio
async def test_patch_member_status_rejects_synthetic_member(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-7; named_risk=member_status_synthetic_member;
    level=particular-integration; source=.tmp/init-124/phase6/step6a-contract.md#C7.
    """
    actor_id = "operator"
    synthetic = synthetic_member_guard_member_factory.synthetic()
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    response = await migrated_async_client.patch(
        f"{BASE_URL}/{synthetic.id}/status",
        json={
            "status": "suspended",
            "reason": "operator requested",
            "originating_actor_kind": "user",
            "originating_actor_id": actor_id,
        },
        headers={**_actor_headers(actor_id=actor_id), "If-Match": '"1"'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "member_status_synthetic_not_allowed"


@pytest.mark.asyncio
async def test_patch_member_status_returns_412_on_stale_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    created_response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )
    created = MemberRead.model_validate(created_response.json())

    first_patch = await migrated_async_client.patch(
        f"{BASE_URL}/{created.id}/status",
        json={
            "status": "suspended",
            "reason": "operator requested",
            "originating_actor_kind": "user",
            "originating_actor_id": actor_id,
        },
        headers={**_actor_headers(actor_id=actor_id), "If-Match": created_response.headers["etag"]},
    )
    assert first_patch.status_code == HTTPStatus.OK, first_patch.text

    stale_patch = await migrated_async_client.patch(
        f"{BASE_URL}/{created.id}/status",
        json={
            "status": "departed",
            "reason": "operator requested",
            "originating_actor_kind": "user",
            "originating_actor_id": actor_id,
        },
        headers={**_actor_headers(actor_id=actor_id), "If-Match": created_response.headers["etag"]},
    )

    assert stale_patch.status_code == HTTPStatus.PRECONDITION_FAILED, stale_patch.text


@pytest.mark.asyncio
async def test_create_member_preserves_originating_user_in_audit(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id="1001",
        ),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    audit_row = _fetch_latest_member_audit(governance_dsn)
    assert audit_row["actor_kind"] == "user"
    assert audit_row["actor_id"] == actor_id
    assert audit_row["request_json"]["discord_user_id"] == discord_user_id
    assert audit_row["request_json"]["originating_actor_kind"] == "user"
    assert audit_row["request_json"]["originating_actor_id"] == "1001"


def test_no_hardcoded_system_actor_in_members_service() -> None:
    service_path = Path(__file__).resolve().parents[1] / "app/services/members.py"
    source = service_path.read_text()

    assert '"system"' not in source
    assert "'system'" not in source


@pytest.mark.asyncio
async def test_unique_discord_user_id_enforced(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    actor_id = "operator"
    discord_user_id = str(uuid4())
    joined_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    _grant_permissions(
        governance_db,
        actor_id=actor_id,
        permissions=frozenset({"member.write"}),
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=_member_payload(
            discord_user_id=discord_user_id,
            joined_at=joined_at,
            originating_actor_id=actor_id,
        ),
        headers=_actor_headers(actor_id=actor_id),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(governance_dsn, autocommit=True) as conn:
            conn.execute(
                """
                INSERT INTO members (id, discord_user_id, joined_at, status, kind)
                VALUES (%s, %s, %s, 'active', 'discord')
                """,
                (uuid4(), discord_user_id, joined_at),
            )
