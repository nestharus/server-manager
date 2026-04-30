from __future__ import annotations

from copy import deepcopy
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.applications import validate_application_responses
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


def _global_chapter_selector_payload() -> dict[str, Any]:
    return {
        "name": "Global Chapter Selector Application",
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "global", "scope_id": None},
        "fields": [
            {
                "id": "chapter",
                "type": "chapter_select",
                "label": "Chapter",
                "required": True,
                "placeholder": "Choose a chapter",
            },
            {
                "id": "character_name",
                "type": "short",
                "label": "Character name",
                "required": True,
                "max_length": 64,
            },
            {
                "id": "application_text",
                "type": "long",
                "label": "Application text",
                "required": True,
                "max_length": 4000,
            },
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": None,
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


@pytest.mark.asyncio
async def test_publish_form_normalizes_scope_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant(governance_db)
    response = await migrated_async_client.post(
        FORMS_URL,
        json=_payload(scope_id="  chapter-1  "),
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()["scope"]["scope_id"] == "chapter-1"
    assert response.json()["routing_rules"]["review_scope"]["scope_id"] == "chapter-1"


@pytest.mark.asyncio
async def test_publish_form_with_chapter_select_round_trips(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=chapter_select_form_contract_roundtrip; level=contract;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)
    payload = _global_chapter_selector_payload()

    published = await migrated_async_client.post(
        FORMS_URL,
        json=payload,
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert published.status_code == HTTPStatus.CREATED, published.text
    current = await migrated_async_client.get(
        f"{FORMS_URL}/current",
        params={"scope_kind": "global"},
        headers=_headers(),
    )
    assert current.status_code == HTTPStatus.OK, current.text
    fields = current.json()["fields"]
    assert fields[0] == payload["fields"][0]
    assert [field["type"] for field in fields] == ["chapter_select", "short", "long"]
    assert current.json()["scope"] == {"scope_kind": "global", "scope_id": None}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda body: body["fields"].insert(
                1,
                {
                    "id": "second_chapter",
                    "type": "chapter_select",
                    "label": "Second chapter",
                    "required": True,
                },
            ),
            id="duplicate",
        ),
        pytest.param(
            lambda body: body["fields"][0].update({"required": False}),
            id="required-false",
        ),
        pytest.param(
            lambda body: body.update(
                {
                    "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
                    "routing_rules": {
                        "schema_version": 1,
                        "queue": "chapter_officers",
                        "review_scope": {
                            "scope_kind": "chapter",
                            "scope_id": "chapter-1",
                        },
                    },
                }
            ),
            id="non-global",
        ),
        pytest.param(
            lambda body: body["fields"][0].update({"id": ""}),
            id="blank-id",
        ),
        pytest.param(
            lambda body: body["fields"][0].update({"label": ""}),
            id="blank-label",
        ),
        pytest.param(
            lambda body: body["routing_rules"].update(
                {"review_scope": {"scope_kind": "global", "scope_id": None}}
            ),
            id="conflicting-review-scope",
        ),
    ],
)
async def test_publish_form_rejects_invalid_chapter_select_contract_shapes(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    mutate,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=chapter_select_form_contract_roundtrip; level=contract;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)
    body = _global_chapter_selector_payload()
    mutate(body)

    response = await migrated_async_client.post(
        FORMS_URL,
        json=body,
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_validate_application_responses_uses_typeadapter_for_union() -> None:
    """Risk annotation: group=TG-1;
    named_risk=chapter_select_form_contract_roundtrip; level=contract;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-1-F1.
    """
    fields: list[dict[str, Any]] = [
        {
            "id": "short_answer",
            "type": "short",
            "label": "Short answer",
            "required": True,
            "max_length": 64,
        },
        {
            "id": "long_answer",
            "type": "long",
            "label": "Long answer",
            "required": True,
            "max_length": 4000,
        },
        {
            "id": "raid_count",
            "type": "number",
            "label": "Raid count",
            "required": True,
        },
        {
            "id": "class",
            "type": "select",
            "label": "Class",
            "required": True,
            "options": ["warrior", "mage"],
        },
        {
            "id": "roles",
            "type": "multi_select",
            "label": "Roles",
            "required": True,
            "options": ["tank", "healer", "damage"],
        },
        {
            "id": "rules",
            "type": "boolean",
            "label": "Rules accepted",
            "required": True,
        },
        {
            "id": "chapter",
            "type": "chapter_select",
            "label": "Chapter",
            "required": True,
            "placeholder": "Choose a chapter",
        },
    ]
    reparsed_fields = deepcopy(fields)

    validate_application_responses(
        reparsed_fields,
        {
            "short_answer": "Kalec",
            "long_answer": "I want to join scheduled guild activities.",
            "raid_count": 3,
            "class": "mage",
            "roles": ["damage"],
            "rules": True,
            "chapter": "chapter-1",
        },
    )
