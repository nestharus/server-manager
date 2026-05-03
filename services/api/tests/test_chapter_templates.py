from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChapterTemplateCreate,
    ChapterTemplatePatch,
    StaleTemplateVersionError,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


TEMPLATES_URL = "/api/v1/chapter-templates"
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


def _seed_template_grants(db: PostgresDatabase) -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db,
            grantee_id="operator",
            scope_kind="global",
            scope_id=None,
            permissions=frozenset({"chapter_template.read", "chapter_template.write"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _chapter_templates_service(app: Any) -> Any:
    from app.services.chapter_templates import ChapterTemplatesService

    service = app.state.container.services.chapter_templates()
    assert isinstance(service, ChapterTemplatesService)
    return service


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


def test_create_chapter_template_creates_new_family_version_1(
    client: TestClient,
    governance_dsn: str,
    governance_db: PostgresDatabase,
) -> None:
    _seed_template_grants(governance_db)

    body = _create_template(client)

    assert body["version"] == 1
    assert body["template_family_id"] == body["id"]
    with psycopg.connect(governance_dsn) as conn:
        row = conn.execute(
            "SELECT template_family_id, version FROM chapter_templates WHERE id = %s",
            (UUID(str(body["id"])),),
        ).fetchone()
    assert row is not None
    assert str(row[0]) == body["id"]
    assert row[1] == 1


def test_patch_chapter_template_creates_new_version_same_family(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_template_grants(governance_db)
    created = _create_template(client)

    patched = client.patch(
        f"{TEMPLATES_URL}/{created['id']}",
        json={"expected_current_version": 1, "name": "Starter Chapter v2"},
        headers=ACTOR_HEADERS,
    )

    assert patched.status_code == HTTPStatus.OK, patched.text
    body = patched.json()
    assert body["id"] != created["id"]
    assert body["template_family_id"] == created["template_family_id"]
    assert body["version"] == 2
    assert body["name"] == "Starter Chapter v2"


def test_patch_chapter_template_stale_expected_version_returns_412(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    _seed_template_grants(governance_db)
    created = _create_template(client)
    first = client.patch(
        f"{TEMPLATES_URL}/{created['id']}",
        json={"expected_current_version": 1, "name": "Starter Chapter v2"},
        headers=ACTOR_HEADERS,
    )
    assert first.status_code == HTTPStatus.OK, first.text

    stale = client.patch(
        f"{TEMPLATES_URL}/{created['id']}",
        json={"expected_current_version": 1, "name": "Starter Chapter v3"},
        headers=ACTOR_HEADERS,
    )

    assert stale.status_code == HTTPStatus.PRECONDITION_FAILED


def test_patch_race_one_accepted_one_412_no_integrityerror(
    app: Any,
    governance_db: PostgresDatabase,
) -> None:
    actor = ActorIdentity(actor_kind="user", actor_id="operator")
    request = ChapterTemplateCreate.model_validate(_template_payload())
    with use_audit_context(_audit_context()):
        created, _ = _chapter_templates_service(app).create_chapter_template(
            request,
            actor,
        )

    def patch(name: str) -> str:
        try:
            with use_audit_context(_audit_context()):
                _chapter_templates_service(app).patch_chapter_template(
                    created.id,
                    ChapterTemplatePatch(expected_current_version=1, name=name),
                    actor,
                )
            return "accepted"
        except StaleTemplateVersionError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(patch, ["v2-a", "v2-b"]))

    assert results == ["accepted", "stale"]

