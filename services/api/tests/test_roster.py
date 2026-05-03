from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.roster import RosterEntryTransitionRequest
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.members import MembersRepository
from app.repositories.roster import RosterRepository
from app.services.mutations import mutate_entity
from app.services.roster import RosterService
from tests._authority_helpers import grant_authority


ROSTER_URL = "/api/v1/roster-entries"
ACTOR_HEADERS = {"X-Actor-Kind": "user", "X-Actor-Id": "operator"}
SERVICE_HEADERS = {"X-Actor-Kind": "service", "X-Actor-Id": "roster-syncer"}


def _audit_context() -> AuditContextRead:
    cid = uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=None,
        headers=CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None),
    )


def _roster_service(db: PostgresDatabase) -> RosterService:
    return RosterService(
        roster_repo=RosterRepository(db),
        members_repo=MembersRepository(db),
        deferred_effects_repo=DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


@pytest.fixture
def governance_db(governance_dsn: str) -> PostgresDatabase:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _seed_grant(
    db: PostgresDatabase,
    *,
    grantee_id: str = "operator",
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
    permissions: frozenset[str] = frozenset(
        {"roster.read", "roster.write", "roster.remove"}
    ),
) -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _seed_roster_syncer_grant(db: PostgresDatabase) -> None:
    _seed_grant(
        db,
        grantee_id="roster-syncer",
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"roster.read", "roster.write"}),
    )


def _seed_chapter_and_roles(
    db: PostgresDatabase,
    *,
    chapter_id: str = "ch-1",
) -> dict[str, UUID]:
    template_id = uuid4()
    member_role_id = uuid4()
    officer_role_id = uuid4()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO chapter_templates (
                id,
                template_family_id,
                version,
                name,
                schema_version,
                channel_structure,
                role_structure,
                default_permission_intents
            )
            VALUES (%s, %s, 1, %s, 1, %s, %s, %s)
            """,
            (
                template_id,
                template_id,
                f"Template {chapter_id}",
                Jsonb([]),
                Jsonb(
                    [
                        {
                            "name": "member",
                            "ordinal": 10,
                            "triggers_succession": False,
                        },
                        {
                            "name": "officer",
                            "ordinal": 20,
                            "triggers_succession": True,
                        },
                    ]
                ),
                Jsonb([]),
            ),
        )
        conn.execute(
            """
            INSERT INTO chapters (
                id,
                name,
                template_id,
                template_snapshot,
                configuration,
                state,
                discord_resources
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s)
            """,
            (
                chapter_id,
                f"Chapter {chapter_id}",
                template_id,
                Jsonb({"role_structure": [{"name": "member"}, {"name": "officer"}]}),
                Jsonb({}),
                Jsonb(
                    {
                        "role_ids": {
                            "member": "discord-role-1",
                            "officer": "discord-role-2",
                        }
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO chapter_roles (
                id,
                chapter_id,
                template_id,
                name,
                ordinal,
                triggers_succession
            )
            VALUES
                (%s, %s, NULL, 'member', 10, false),
                (%s, %s, NULL, 'officer', 20, true)
            """,
            (member_role_id, chapter_id, officer_role_id, chapter_id),
        )
    return {"member": member_role_id, "officer": officer_role_id}


def _seed_real_roster_member(db: PostgresDatabase) -> str:
    member_id = uuid4()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO members (id, discord_user_id, joined_at, status, kind)
            VALUES (%s, %s, %s, 'active', 'discord')
            """,
            (member_id, str(10**17 + (uuid4().int % 10**17)), datetime.now(UTC)),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type, aggregate_id, current_seq, latest_change_id
            )
            VALUES ('member', %s, 1, NULL)
            """,
            (str(member_id),),
        )
    return str(member_id)


def _create_entry(
    client: TestClient,
    db: PostgresDatabase,
    role_id: UUID,
    *,
    member_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    roster_member_id = member_id or _seed_real_roster_member(db)
    response = client.post(
        ROSTER_URL,
        json={
            "chapter_id": "ch-1",
            "member_id": roster_member_id,
            "role_id": str(role_id),
        },
        headers=headers or ACTOR_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json(), response.headers["etag"]


def _transition(
    client: TestClient,
    entry_id: str,
    etag: str,
    to_status: str,
    *,
    role_id: UUID | None = None,
    reason: str = "operator requested",
    originating_actor_id: str = "1001",
) -> tuple[dict[str, Any], str, int]:
    payload: dict[str, Any] = {
        "to_status": to_status,
        "reason": reason,
        "originating_actor_kind": "user",
        "originating_actor_id": originating_actor_id,
    }
    if role_id is not None:
        payload["to_role_id"] = str(role_id)
    response = client.post(
        f"{ROSTER_URL}/{entry_id}/transitions",
        json=payload,
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    return response.json(), response.headers.get("etag", ""), response.status_code


def _latest_transition_id(dsn: str, entry_id: str) -> str:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM roster_transitions
            WHERE roster_entry_id = %s
            ORDER BY aggregate_seq DESC
            LIMIT 1
            """,
            (entry_id,),
        ).fetchone()
    assert row is not None
    return str(row["id"])


def _record_sync_failure(
    client: TestClient,
    entry_id: str,
    etag: str,
    transition_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str, int]:
    response = client.post(
        f"{ROSTER_URL}/{entry_id}/sync-failure",
        json={
            "transition_id": transition_id,
            "reason": "Forbidden",
            "member_discord_user_id": "1234",
            "operation": "add_roles",
            "failed_at_step": "discord_add_roles",
            "desired_discord_role_ids": ["discord-role-1"],
            "error_type": "Forbidden",
            "originating_actor_kind": "service",
            "originating_actor_id": "roster-syncer",
        },
        headers={**(headers or SERVICE_HEADERS), "If-Match": etag},
    )
    return response.json(), response.headers.get("etag", ""), response.status_code


def test_create_roster_entry_in_active_state(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-6; named_risk=roster_real_member_regression;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C6.
    """
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)

    body, etag = _create_entry(client, governance_db, roles["member"])

    assert body["status"] == "active"
    assert body["version"] == 1
    assert body["removal_metadata"] == {}
    assert etag == '"1"'


def test_create_roster_entry_rejects_synthetic_member(
    client: TestClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-6; named_risk=roster_entry_synthetic_member;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C6.
    """
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    synthetic = synthetic_member_guard_member_factory.synthetic()

    response = client.post(
        ROSTER_URL,
        json={
            "chapter_id": "ch-1",
            "member_id": str(synthetic.id),
            "role_id": str(roles["member"]),
        },
        headers=ACTOR_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "roster_member_synthetic_not_allowed"


def test_create_roster_entry_requires_roster_write_permission_chapter_scope(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(
        governance_db,
        permissions=frozenset({"roster.read"}),
    )

    response = client.post(
        ROSTER_URL,
        json={
            "chapter_id": "ch-1",
            "member_id": "member-1",
            "role_id": str(roles["member"]),
        },
        headers=ACTOR_HEADERS,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "authority_decision_denied"


def test_create_roster_entry_duplicate_active_returns_409(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, _etag = _create_entry(client, governance_db, roles["member"])

    duplicate = client.post(
        ROSTER_URL,
        json={
            "chapter_id": "ch-1",
            "member_id": entry["member_id"],
            "role_id": str(roles["member"]),
        },
        headers=ACTOR_HEADERS,
    )

    assert duplicate.status_code == HTTPStatus.CONFLICT
    assert duplicate.json()["code"] == "duplicate_current_roster_entry"


def test_transition_creates_roster_transition_row_with_actor(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])

    body, next_etag, status = _transition(
        client,
        entry["id"],
        etag,
        "on_leave",
        role_id=roles["officer"],
    )

    assert status == HTTPStatus.OK
    assert body["status"] == "on_leave"
    assert next_etag == '"2"'
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT aggregate_seq, from_status, to_status, from_role_id, to_role_id,
                   actor_kind, actor_id
            FROM roster_transitions
            WHERE roster_entry_id = %s
            """,
            (entry["id"],),
        ).fetchone()
    assert row is not None
    assert row["aggregate_seq"] == 2
    assert row["from_status"] == "active"
    assert row["to_status"] == "on_leave"
    assert row["from_role_id"] == roles["member"]
    assert row["to_role_id"] == roles["officer"]
    assert row["actor_kind"] == "user"
    assert row["actor_id"] == "operator"


def test_transition_records_reason_and_originating_user(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])

    _transition(
        client,
        entry["id"],
        etag,
        "under_review",
        reason="manual review",
        originating_actor_id="9999",
    )

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT reason, originating_actor_kind, originating_actor_id
            FROM roster_transitions
            WHERE roster_entry_id = %s
            """,
            (entry["id"],),
        ).fetchone()
    assert row is not None
    assert row["reason"] == "manual review"
    assert row["originating_actor_kind"] == "user"
    assert row["originating_actor_id"] == "9999"


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("active", "on_leave"),
        ("active", "under_review"),
        ("active", "removed"),
        ("on_leave", "active"),
        ("on_leave", "removed"),
        ("under_review", "active"),
        ("under_review", "removed"),
    ],
)
def test_transition_allowed_state_pairs(
    client: TestClient,
    governance_db: PostgresDatabase,
    from_status: str,
    to_status: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    if from_status != "active":
        entry, etag, status = _transition(client, entry["id"], etag, from_status)
        assert status == HTTPStatus.OK

    body, _, status = _transition(client, entry["id"], etag, to_status)

    assert status == HTTPStatus.OK, body
    assert body["status"] == to_status


@pytest.mark.parametrize(
    ("setup_status", "to_status"),
    [
        ("active", "active"),
        ("on_leave", "under_review"),
        ("under_review", "on_leave"),
        ("removed", "active"),
    ],
)
def test_transition_disallowed_state_pairs_return_409(
    client: TestClient,
    governance_db: PostgresDatabase,
    setup_status: str,
    to_status: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    if setup_status != "active":
        entry, etag, status = _transition(client, entry["id"], etag, setup_status)
        assert status == HTTPStatus.OK

    body, _, status = _transition(client, entry["id"], etag, to_status)

    assert status == HTTPStatus.CONFLICT
    assert body["code"] == "invalid_roster_transition"


def test_transition_role_only_same_status_succeeds(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])

    body, next_etag, status = _transition(
        client,
        entry["id"],
        etag,
        "active",
        role_id=roles["officer"],
    )

    assert status == HTTPStatus.OK
    assert body["status"] == "active"
    assert body["role_id"] == str(roles["officer"])
    assert body["version"] == 2
    assert next_etag == '"2"'


def test_transition_same_status_same_role_returns_409(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])

    body, _, status = _transition(
        client,
        entry["id"],
        etag,
        "active",
        role_id=roles["member"],
    )

    assert status == HTTPStatus.CONFLICT
    assert body["code"] == "invalid_roster_transition"


def test_removed_is_terminal(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    removed, etag, status = _transition(client, entry["id"], etag, "removed")
    assert status == HTTPStatus.OK
    assert removed["status"] == "removed"

    body, _, status = _transition(client, entry["id"], etag, "active")

    assert status == HTTPStatus.CONFLICT
    assert body["code"] == "invalid_roster_transition"


def test_transition_with_current_version_succeeds(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])

    body, next_etag, status = _transition(client, entry["id"], etag, "on_leave")

    assert status == HTTPStatus.OK
    assert body["version"] == 2
    assert next_etag == '"2"'


def test_transition_with_stale_version_returns_412(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    _transition(client, entry["id"], etag, "on_leave")

    response = client.post(
        f"{ROSTER_URL}/{entry['id']}/transitions",
        json={
            "to_status": "on_leave",
            "reason": "retry stale",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED


def test_get_roster_entry_returns_version_and_etag(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, _ = _create_entry(client, governance_db, roles["member"])

    response = client.get(f"{ROSTER_URL}/{entry['id']}", headers=ACTOR_HEADERS)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["version"] == 1
    assert response.headers["etag"] == '"1"'


def test_transition_roster_entry_accepts_shared_connection(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: roster transitions can participate in a caller-owned transaction and roll back atomically."""
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, _ = _create_entry(client, governance_db, roles["member"])
    entry_id = UUID(entry["id"])
    service = _roster_service(governance_db)

    with pytest.raises(RuntimeError, match="force rollback"):
        with use_audit_context(_audit_context()):
            with governance_db.transaction() as connection:
                current, _etag = service._get_roster_entry_on(
                    connection,
                    entry_id,
                )
                service._transition_roster_entry_on(
                    connection,
                    entry_id,
                    RosterEntryTransitionRequest(
                        to_status="under_review",
                        reason="shared tx",
                        originating_actor_kind="user",
                        originating_actor_id="operator",
                    ),
                    ActorIdentity(actor_kind="user", actor_id="operator"),
                    current.version,
                )
                row = connection.execute(
                    "SELECT status FROM roster_entries WHERE id = %s",
                    (entry_id,),
                ).fetchone()
                assert row is not None
                assert row[0] == "under_review"
                raise RuntimeError("force rollback")

    rolled_back, _rolled_back_etag = service.get_roster_entry(entry_id)
    assert rolled_back.status == "active"


def test_sync_failure_enqueues_deferred_effect_atomically(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    _seed_roster_syncer_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    entry, etag, status = _transition(client, entry["id"], etag, "on_leave")
    assert status == HTTPStatus.OK
    transition_id = _latest_transition_id(governance_dsn, entry["id"])

    body, next_etag, status = _record_sync_failure(
        client, entry["id"], etag, transition_id
    )

    assert status == HTTPStatus.OK
    assert body["version"] == 3
    assert next_etag == '"3"'
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        effect = conn.execute(
            """
            SELECT subsystem, effect_type, consequence_level, precondition_state,
                   idempotency_key
            FROM deferred_effects
            """
        ).fetchone()
        head = conn.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'roster_entry' AND aggregate_id = %s
            """,
            (entry["id"],),
        ).fetchone()
    assert effect is not None
    assert effect["subsystem"] == "roster_role_sync"
    assert effect["effect_type"] == "roster_sync_retry"
    assert effect["consequence_level"] == "consequential"
    assert effect["precondition_state"] == "unchecked"
    assert (
        effect["idempotency_key"] == f"roster_sync_retry:{entry['id']}:{transition_id}"
    )
    assert head["current_seq"] == 3


def test_sync_failure_idempotency_key_per_transition(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    _seed_roster_syncer_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    entry, etag, _ = _transition(client, entry["id"], etag, "on_leave")
    first_transition = _latest_transition_id(governance_dsn, entry["id"])
    _, etag, status = _record_sync_failure(client, entry["id"], etag, first_transition)
    assert status == HTTPStatus.OK
    entry, etag, _ = _transition(client, entry["id"], etag, "active")
    second_transition = _latest_transition_id(governance_dsn, entry["id"])

    _record_sync_failure(client, entry["id"], etag, second_transition)

    with psycopg.connect(governance_dsn) as conn:
        rows = conn.execute(
            "SELECT idempotency_key FROM deferred_effects ORDER BY created_at, id"
        ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]


def test_sync_failure_preserves_roster_entry_state(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    _seed_roster_syncer_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    entry, etag, _ = _transition(client, entry["id"], etag, "under_review")
    transition_id = _latest_transition_id(governance_dsn, entry["id"])

    body, _, status = _record_sync_failure(client, entry["id"], etag, transition_id)

    assert status == HTTPStatus.OK
    assert body["status"] == "under_review"


def test_sync_failure_rejects_non_service_actors_with_403(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    entry, etag, _ = _transition(client, entry["id"], etag, "on_leave")
    transition_id = _latest_transition_id(governance_dsn, entry["id"])

    body, _, status = _record_sync_failure(
        client,
        entry["id"],
        etag,
        transition_id,
        headers=ACTOR_HEADERS,
    )

    assert status == HTTPStatus.FORBIDDEN
    assert body["code"] == "service_actor_required"


def test_sync_failure_accepts_roster_syncer_service_actor_with_global_grant(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    _seed_roster_syncer_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    entry, etag, _ = _transition(client, entry["id"], etag, "on_leave")
    transition_id = _latest_transition_id(governance_dsn, entry["id"])

    _, _, status = _record_sync_failure(client, entry["id"], etag, transition_id)

    assert status == HTTPStatus.OK


def test_partial_unique_index_allows_one_active_per_chapter_member(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    roles = _seed_chapter_and_roles(governance_db)
    _seed_grant(governance_db)
    entry, etag = _create_entry(client, governance_db, roles["member"])
    duplicate = client.post(
        ROSTER_URL,
        json={
            "chapter_id": "ch-1",
            "member_id": entry["member_id"],
            "role_id": str(roles["member"]),
        },
        headers=ACTOR_HEADERS,
    )
    assert duplicate.status_code == HTTPStatus.CONFLICT
    _, _, status = _transition(client, entry["id"], etag, "removed")
    assert status == HTTPStatus.OK

    replacement, _ = _create_entry(client, governance_db, roles["member"])

    assert replacement["status"] == "active"
    assert replacement["id"] != entry["id"]


def test_roster_syncer_service_actor_grants_seeded(
    fresh_migrated_postgres_db: str,
) -> None:
    with psycopg.connect(fresh_migrated_postgres_db) as conn:
        row = conn.execute(
            """
            SELECT permissions
            FROM authority_grants
            WHERE grantee_id = 'roster-syncer'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND revoked_at IS NULL
            """
        ).fetchone()
    assert row is not None
    assert set(row[0]) >= {"roster.read", "roster.write"}


def test_no_legacy_insert_roster_entry_remains() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    forbidden = (
        "def insert_roster_entry(",
        "def fetch_roster_entry(",
        "def update_roster_status(",
        "def read_roster_entry(",
        "def transition_roster_status(",
        "roster-service",
    )
    for path in app_root.rglob("*.py"):
        text = path.read_text()
        assert all(needle not in text for needle in forbidden), path
