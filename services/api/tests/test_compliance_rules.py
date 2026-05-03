from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.repositories.db import PostgresDatabase

from .compliance_helpers import RULES_URL, create_rule_http, fetch_one, grant


pytestmark = pytest.mark.usefixtures("governance_dsn")


def test_create_rule_persists_contract_fields(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC1: creating a compliance rule persists cadence, evidence requirements, and consequence policy."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write"}),
    )

    body, etag = create_rule_http(client)

    row = fetch_one(
        governance_dsn,
        "SELECT chapter_id, cadence_kind, evidence_requirements, consequence_kind FROM compliance_rules WHERE id = %s",
        (body["id"],),
    )
    assert body["chapter_id"] == "ch-1"
    assert body["version"] == 1
    assert etag == '"1"'
    assert row["chapter_id"] == "ch-1"
    assert row["cadence_kind"] == "weekly"
    assert row["evidence_requirements"] == [{"type": "attendance", "required": True}]
    assert row["consequence_kind"] == "review"


def test_update_rule_uses_occ_and_advances_version(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC1: updating a compliance rule requires a strong If-Match and advances the version on success."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write"}),
    )

    created, etag = create_rule_http(client)
    response = client.patch(
        f"{RULES_URL}/{created['id']}",
        json={"evaluation_window_days": 14},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["evaluation_window_days"] == 14
    assert response.json()["version"] == 2
    assert response.headers["etag"] == '"2"'


def test_duplicate_active_rule_name_conflicts(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC1: a second active rule with the same chapter/name pair is rejected."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write"}),
    )

    create_rule_http(client, name="Drill Attendance")
    response = client.post(
        RULES_URL,
        json={
            "chapter_id": "ch-1",
            "name": "Drill Attendance",
            "cadence_kind": "weekly",
            "cadence_params": {},
            "evaluation_window_days": 7,
            "evidence_requirements": [{"type": "attendance", "required": True}],
            "consequence_kind": "review",
            "consequence_params": {},
        },
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "duplicate_active_compliance_rule"


def test_archive_allows_name_reuse(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC1: archiving a rule frees the chapter/name slot so a replacement rule can be created."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write"}),
    )

    created, etag = create_rule_http(client, name="Name Reuse")
    archive = client.patch(
        f"{RULES_URL}/{created['id']}",
        json={"active": False},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": etag},
    )
    recreated, _new_etag = create_rule_http(client, name="Name Reuse")

    assert archive.status_code == HTTPStatus.OK, archive.text
    assert archive.json()["active"] is False
    assert archive.json()["archived_at"] is not None
    assert recreated["id"] != created["id"]


def test_list_rules_is_chapter_scoped(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC1: listing rules returns only the authorized chapter scope."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write", "compliance_rule.read"}),
    )
    grant(
        db,
        grantee_id="operator",
        permissions=frozenset({"compliance_rule.write", "compliance_rule.read"}),
        scope_id="ch-2",
    )

    create_rule_http(client, chapter_id="ch-1", name="Chapter One")
    create_rule_http(client, chapter_id="ch-2", name="Chapter Two")

    response = client.get(
        RULES_URL,
        params={"chapter_id": "ch-1"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert [item["name"] for item in response.json()] == ["Chapter One"]
