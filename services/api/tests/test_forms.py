from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


FORMS_URL = "/api/v1/application-forms"


def _headers(actor_id: str = "operator", **extra: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id, **extra}


def _audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _grant(db: PostgresDatabase, *, actor_id: str = "operator") -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
            permissions=frozenset({"application_form.publish"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _payload(*, scope_id: str = "chapter-1", name: str = "Chapter Application") -> dict[str, Any]:
    return {
        "name": name,
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "chapter", "scope_id": scope_id},
        "fields": [
            {
                "id": "nickname",
                "type": "short",
                "label": "Nickname",
                "required": True,
                "max_length": 64,
            },
            {
                "id": "class",
                "type": "select",
                "label": "Class",
                "required": False,
                "options": ["warrior", "mage"],
            },
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "chapter", "scope_id": scope_id},
        },
    }


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_publish_form_versions_and_current_lookup(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant(governance_db)
    first = await migrated_async_client.post(
        FORMS_URL,
        json=_payload(name="First"),
        headers=_headers(**{"If-Match": '"0"'}),
    )
    assert first.status_code == HTTPStatus.CREATED, first.text
    assert first.headers["etag"] == '"1"'
    assert first.json()["version"] == 1

    second = await migrated_async_client.post(
        FORMS_URL,
        json=_payload(name="Second"),
        headers=_headers(**{"If-Match": first.headers["etag"]}),
    )
    assert second.status_code == HTTPStatus.CREATED, second.text
    assert second.headers["etag"] == '"2"'
    assert second.json()["version"] == 2

    current = await migrated_async_client.get(
        f"{FORMS_URL}/current",
        params={"scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_headers(),
    )
    assert current.status_code == HTTPStatus.OK, current.text
    assert current.json()["name"] == "Second"
    assert current.headers["etag"] == '"2"'

    other_scope = await migrated_async_client.post(
        FORMS_URL,
        json=_payload(scope_id="chapter-2", name="Other"),
        headers=_headers(**{"If-Match": '"0"'}),
    )
    assert other_scope.status_code == HTTPStatus.CREATED, other_scope.text
    assert other_scope.json()["version"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.update({"fields": []}),
        lambda body: body["fields"].append({**body["fields"][0]}),
        lambda body: body["fields"][0].update({"id": "Bad"}),
        lambda body: body["fields"][0].update({"label": " "}),
        lambda body: body["fields"][0].update({"type": "number", "max_length": 5}),
        lambda body: body["fields"][1].update({"options": []}),
        lambda body: body["routing_rules"].update({"queue": "other"}),
        lambda body: body.update({"scope": {"scope_kind": "global", "scope_id": "x"}}),
    ],
)
async def test_publish_form_rejects_invalid_contract_shapes(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    mutate,
) -> None:
    _grant(governance_db)
    body = _payload()
    mutate(body)

    response = await migrated_async_client.post(
        FORMS_URL,
        json=body,
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
