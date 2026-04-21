from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.chapter_templates import CURRENT_TEMPLATE_SCHEMA_VERSION
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


TEMPLATES_URL = "/api/v1/chapter-templates"
CHAPTERS_URL = "/api/v1/chapters"
ACTOR_HEADERS = {"X-Actor-Kind": "user", "X-Actor-Id": "operator"}


def _audit_context() -> AuditContextRead:
    cid = uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=None,
        headers=CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None),
    )


@pytest.fixture()
def governance_db(governance_dsn: str) -> PostgresDatabase:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _seed_grants(db: PostgresDatabase) -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db,
            grantee_id="operator",
            scope_kind="global",
            scope_id=None,
            permissions=frozenset(
                {
                    "chapter_template.read",
                    "chapter_template.write",
                    "chapter.read",
                    "chapter.write",
                }
            ),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _template_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Starter Chapter",
        "schema_version": CURRENT_TEMPLATE_SCHEMA_VERSION,
        "channel_structure": [
            {"name": "announcements", "type": "text", "topic": "Chapter news"},
            {"name": "general", "type": "text"},
        ],
        "role_structure": [
            {"name": "officer", "ordinal": 10, "triggers_succession": True},
            {"name": "member", "ordinal": 20, "triggers_succession": False},
        ],
        "default_permission_intents": [
            {
                "role_name": "member",
                "kind": "guild_role",
                "permission_bits": "2048",
                "temporary": False,
            }
        ],
    }
    payload.update(overrides)
    return payload


def _create_template(client: TestClient) -> dict[str, object]:
    response = client.post(TEMPLATES_URL, json=_template_payload(), headers=ACTOR_HEADERS)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _chapter_payload(template_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Humility Seattle",
        "template_id": template_id,
        "configuration": {},
        "originating_actor_kind": "user",
        "originating_actor_id": "1001",
    }
    payload.update(overrides)
    return payload


def _create_chapter(client: TestClient, template_id: str, **overrides: object) -> tuple[dict[str, object], str]:
    response = client.post(
        CHAPTERS_URL,
        json=_chapter_payload(template_id, **overrides),
        headers=ACTOR_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json(), response.headers["etag"]


def _transition(
    client: TestClient,
    chapter_id: str,
    etag: str,
    to_state: str,
    *,
    reason: str = "operator requested",
) -> tuple[dict[str, object], str, int]:
    response = client.post(
        f"{CHAPTERS_URL}/{chapter_id}/transitions",
        json={
            "to_state": to_state,
            "reason": reason,
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    return response.json(), response.headers.get("etag", ""), response.status_code


def _patch_resources(
    client: TestClient,
    chapter_id: str,
    etag: str,
    resources: dict[str, object],
) -> tuple[dict[str, object], str, int]:
    response = client.patch(
        f"{CHAPTERS_URL}/{chapter_id}/discord-resources",
        json={"resources": resources},
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    return response.json(), response.headers.get("etag", ""), response.status_code


def _ready_resources() -> dict[str, object]:
    return {
        "category_id": "cat-1",
        "role_ids": {"officer": "role-1", "member": "role-2"},
        "channel_ids": {"announcements": "chan-1", "general": "chan-2"},
    }


def test_create_chapter_deep_copies_template_snapshot(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, _ = _create_chapter(client, str(template["id"]))
    patch = client.patch(
        f"{TEMPLATES_URL}/{template['id']}",
        json={"expected_current_version": 1, "name": "Template v2"},
        headers=ACTOR_HEADERS,
    )
    assert patch.status_code == HTTPStatus.OK, patch.text

    current = client.get(f"{CHAPTERS_URL}/{chapter['id']}", headers=ACTOR_HEADERS)

    assert current.status_code == HTTPStatus.OK, current.text
    snapshot = current.json()["template_snapshot"]
    assert snapshot["template_id"] == template["id"]
    assert snapshot["template_version"] == 1
    assert snapshot["channel_structure"] == template["channel_structure"]


def test_create_chapter_in_proposed_state(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))

    assert chapter["state"] == "proposed"
    assert chapter["template_id"] == template["id"]
    assert chapter["discord_resources"] == {
        "category_id": None,
        "role_ids": {},
        "channel_ids": {},
    }
    assert etag == '"1"'


def test_create_chapter_with_nonexistent_template_returns_404(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)

    response = client.post(
        CHAPTERS_URL,
        json=_chapter_payload(str(uuid4())),
        headers=ACTOR_HEADERS,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_create_chapter_duplicate_name_returns_409(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    _create_chapter(client, str(template["id"]))

    duplicate = client.post(
        CHAPTERS_URL,
        json=_chapter_payload(str(template["id"])),
        headers=ACTOR_HEADERS,
    )

    assert duplicate.status_code == HTTPStatus.CONFLICT


def test_transition_proposed_to_provisioning(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))

    body, next_etag, status = _transition(client, str(chapter["id"]), etag, "provisioning")

    assert status == HTTPStatus.OK
    assert body["state"] == "provisioning"
    assert next_etag == '"2"'


def test_transition_provisioning_to_active_persists_discord_resource_ids(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")
    _, etag, status = _patch_resources(client, str(chapter["id"]), etag, _ready_resources())
    assert status == HTTPStatus.OK

    body, _, status = _transition(client, str(chapter["id"]), etag, "active")

    assert status == HTTPStatus.OK
    assert body["state"] == "active"
    assert body["discord_resources"] == _ready_resources()


@pytest.mark.parametrize(
    ("resources", "missing"),
    [
        ({"role_ids": {"officer": "role-1", "member": "role-2"}, "channel_ids": {"announcements": "chan-1", "general": "chan-2"}}, "category"),
        ({"category_id": "cat-1", "role_ids": {"member": "role-2"}, "channel_ids": {"announcements": "chan-1", "general": "chan-2"}}, "roles"),
        ({"category_id": "cat-1", "role_ids": {"officer": "role-1", "member": "role-2"}, "channel_ids": {"general": "chan-2"}}, "channels"),
    ],
)
def test_transition_to_active_rejects_when_incomplete(
    client: TestClient,
    governance_db: PostgresDatabase,
    resources: dict[str, object],
    missing: str,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")
    _, etag, status = _patch_resources(client, str(chapter["id"]), etag, resources)
    assert status == HTTPStatus.OK

    body, _, status = _transition(client, str(chapter["id"]), etag, "active")

    assert status == HTTPStatus.CONFLICT
    assert body["code"] == "incomplete_provisioning"
    assert body["missing"].startswith(missing)


def test_transition_to_active_rejects_when_category_missing(client: TestClient, governance_db: PostgresDatabase) -> None:
    test_transition_to_active_rejects_when_incomplete(client, governance_db, {"role_ids": {"officer": "role-1", "member": "role-2"}, "channel_ids": {"announcements": "chan-1", "general": "chan-2"}}, "category")


def test_transition_to_active_rejects_when_template_role_missing(client: TestClient, governance_db: PostgresDatabase) -> None:
    test_transition_to_active_rejects_when_incomplete(client, governance_db, {"category_id": "cat-1", "role_ids": {"member": "role-2"}, "channel_ids": {"announcements": "chan-1", "general": "chan-2"}}, "roles")


def test_transition_to_active_rejects_when_template_channel_missing(client: TestClient, governance_db: PostgresDatabase) -> None:
    test_transition_to_active_rejects_when_incomplete(client, governance_db, {"category_id": "cat-1", "role_ids": {"officer": "role-1", "member": "role-2"}, "channel_ids": {"general": "chan-2"}}, "channels")


def test_patch_discord_resources_merges_not_replaces(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    first, etag, status = _patch_resources(
        client,
        str(chapter["id"]),
        etag,
        {"category_id": "cat-1", "role_ids": {"officer": "role-1"}},
    )
    assert status == HTTPStatus.OK
    second, _, status = _patch_resources(
        client,
        str(chapter["id"]),
        etag,
        {"role_ids": {"member": "role-2"}, "channel_ids": {"general": "chan-2"}},
    )

    assert status == HTTPStatus.OK
    assert first["discord_resources"]["role_ids"] == {"officer": "role-1"}
    assert second["discord_resources"]["category_id"] == "cat-1"
    assert second["discord_resources"]["role_ids"] == {
        "officer": "role-1",
        "member": "role-2",
    }


def test_patch_discord_resources_requires_if_match(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, _ = _create_chapter(client, str(template["id"]))

    response = client.patch(
        f"{CHAPTERS_URL}/{chapter['id']}/discord-resources",
        json={"resources": {"category_id": "cat-1"}},
        headers=ACTOR_HEADERS,
    )

    assert response.status_code == HTTPStatus.PRECONDITION_REQUIRED


def test_transition_provisioning_to_failed_enqueues_deferred_effect_atomically(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")

    body, _, status = _transition(client, str(chapter["id"]), etag, "provisioning_failed", reason="discord failed")

    assert status == HTTPStatus.OK
    assert body["state"] == "provisioning_failed"
    with psycopg.connect(governance_dsn) as conn:
        row = conn.execute(
            "SELECT effect_type, consequence_level, precondition_state, idempotency_key FROM deferred_effects"
        ).fetchone()
    assert row is not None
    assert row[0] == "chapter_provisioning_retry"
    assert row[1] == "consequential"
    assert row[2] == "unchecked"
    assert row[3].startswith(f"chapter_provision_retry:{chapter['id']}:")


def test_retry_transition_from_provisioning_failed_to_provisioning(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")
    failed, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning_failed")

    retried, _, status = _transition(client, str(failed["id"]), etag, "provisioning")

    assert status == HTTPStatus.OK
    assert retried["state"] == "provisioning"


def test_deferred_effect_idempotency_key_per_transition(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")
    failed, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning_failed")
    retried, etag, _ = _transition(client, str(failed["id"]), etag, "provisioning")
    assert retried["state"] == "provisioning"
    _transition(client, str(chapter["id"]), etag, "provisioning_failed")

    with psycopg.connect(governance_dsn) as conn:
        rows = conn.execute(
            "SELECT idempotency_key FROM deferred_effects ORDER BY created_at, id"
        ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]


def test_provisioning_failed_chapter_row_not_marked_active(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, etag = _create_chapter(client, str(template["id"]))
    _, etag, _ = _transition(client, str(chapter["id"]), etag, "provisioning")
    body, _, _ = _transition(client, str(chapter["id"]), etag, "provisioning_failed")

    assert body["state"] == "provisioning_failed"


def test_api_records_originating_user_discord_id_in_audit_payload(
    client: TestClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _seed_grants(governance_db)
    template = _create_template(client)
    chapter, _ = _create_chapter(client, str(template["id"]), originating_actor_id="9999")

    with psycopg.connect(governance_dsn) as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM activity_state_changes
            WHERE aggregate_type = 'chapter'
              AND aggregate_id = %s
              AND aggregate_seq = 1
            """,
            (chapter["id"],),
        ).fetchone()

    assert row is not None
    assert row[0]["originating_user_discord_id"] == "9999"


def test_no_legacy_inmemorychapterrepository_remains() -> None:
    root = Path(__file__).resolve().parents[1]
    needle = "InMemory" + "ChapterRepository"
    matches = list((root / "app").rglob("*.py"))
    assert all(needle not in path.read_text() for path in matches)


def test_no_chapterstatus_remains() -> None:
    root = Path(__file__).resolve().parents[1]
    needle = "Chapter" + "Status"
    assert all(needle not in path.read_text() for path in (root / "app").rglob("*.py"))


def test_no_archive_route_under_api_v1_chapters() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints" / "chapters.py"
    needle = "/" + "archive"
    assert needle not in root.read_text()


def test_discord_provisioner_service_actor_has_chapter_grants_after_migration(
    fresh_migrated_postgres_db: str,
) -> None:
    with psycopg.connect(fresh_migrated_postgres_db) as conn:
        row = conn.execute(
            """
            SELECT permissions
            FROM authority_grants
            WHERE grantee_id = 'discord-provisioner'
              AND scope_kind = 'global'
              AND scope_id IS NULL
              AND revoked_at IS NULL
            """
        ).fetchone()
    assert row is not None
    assert set(row[0]) >= {"chapter.read", "chapter.write", "chapter_template.read"}
