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
from app.services.applications import _validate_application_responses_impl
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
                "max_length": None,
                "options": None,
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


def _global_conditional_payload(
    fields: list[dict[str, Any]],
    *,
    name: str = "Global Conditional Application",
) -> dict[str, Any]:
    return {
        "name": name,
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "global", "scope_id": None},
        "fields": fields,
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "global", "scope_id": None},
        },
    }


def _global_chapter_conditional_payload(
    fields: list[dict[str, Any]],
    *,
    name: str = "Global Chapter Conditional Application",
) -> dict[str, Any]:
    return {
        "name": name,
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "global", "scope_id": None},
        "fields": fields,
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": None,
        },
    }


def _scalar_source_fields() -> list[dict[str, Any]]:
    return [
        {
            "id": "source_short",
            "type": "short",
            "label": "Source short",
            "required": True,
            "max_length": 64,
            "page": 1,
        },
        {
            "id": "source_long",
            "type": "long",
            "label": "Source long",
            "required": False,
            "max_length": 4000,
            "page": 1,
        },
        {
            "id": "source_number",
            "type": "number",
            "label": "Source number",
            "required": False,
            "page": 2,
        },
        {
            "id": "source_select",
            "type": "select",
            "label": "Source select",
            "required": False,
            "options": ["yes", "no"],
            "page": 2,
        },
        {
            "id": "source_boolean",
            "type": "boolean",
            "label": "Source boolean",
            "required": False,
            "page": 3,
        },
    ]


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
async def test_publish_form_with_pages_and_visible_when_round_trips(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=visible_when_contract_roundtrip_and_publish_validator;
    level=contract;
    source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)
    fields = [
        {
            "id": "chapter",
            "type": "chapter_select",
            "label": "Chapter",
            "required": True,
            "placeholder": "Choose a chapter",
            "page": 1,
        },
        *_scalar_source_fields(),
        {
            "id": "dependent_long",
            "type": "long",
            "label": "Dependent long",
            "required": False,
            "max_length": 4000,
            "page": 4,
            "visible_when": {"field_id": "source_short", "op": "eq", "value": "yes"},
        },
        {
            "id": "dependent_number",
            "type": "number",
            "label": "Dependent number",
            "required": False,
            "page": 5,
            "visible_when": {"field_id": "source_long", "op": "neq", "value": "skip"},
        },
        {
            "id": "dependent_select",
            "type": "select",
            "label": "Dependent select",
            "required": False,
            "options": ["alpha", "bravo"],
            "page": 5,
            "visible_when": {"field_id": "source_number", "op": "in", "value": [1, 2]},
        },
        {
            "id": "dependent_boolean",
            "type": "boolean",
            "label": "Dependent boolean",
            "required": False,
            "page": 6,
            "visible_when": {
                "field_id": "source_select",
                "op": "not_in",
                "value": ["no"],
            },
        },
        {
            "id": "dependent_short",
            "type": "short",
            "label": "Dependent short",
            "required": False,
            "max_length": 64,
            "page": 9,
            "visible_when": {"field_id": "source_boolean", "op": "eq", "value": True},
        },
    ]

    published = await migrated_async_client.post(
        FORMS_URL,
        json=_global_chapter_conditional_payload(fields),
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert published.status_code == HTTPStatus.CREATED, published.text
    current = await migrated_async_client.get(
        f"{FORMS_URL}/current",
        params={"scope_kind": "global"},
        headers=_headers(),
    )
    assert current.status_code == HTTPStatus.OK, current.text
    round_tripped_fields = current.json()["fields"]
    assert [field["page"] for field in round_tripped_fields] == [
        field["page"] for field in fields
    ]
    assert {
        field["id"]: field.get("visible_when")
        for field in round_tripped_fields
        if field["id"].startswith("dependent_")
    } == {
        field["id"]: field["visible_when"]
        for field in fields
        if field["id"].startswith("dependent_")
    }
    assert round_tripped_fields[0]["type"] == "chapter_select"
    assert round_tripped_fields[0].get("visible_when") is None


@pytest.mark.asyncio
async def test_publish_form_with_file_field_round_trips(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)
    fields = [
        {
            "id": "has_character_sheet",
            "type": "boolean",
            "label": "Has character sheet",
            "required": True,
            "page": 1,
        },
        {
            "id": "character_sheet",
            "type": "file",
            "label": "Character sheet",
            "required": True,
            "accept": ["image/png", "application/pdf"],
            "max_size_bytes": 1_048_576,
            "page": 2,
            "visible_when": {
                "field_id": "has_character_sheet",
                "op": "eq",
                "value": True,
            },
        },
    ]

    published = await migrated_async_client.post(
        FORMS_URL,
        json=_global_conditional_payload(
            fields,
            name="Global File Upload Application",
        ),
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert published.status_code == HTTPStatus.CREATED, published.text
    current = await migrated_async_client.get(
        f"{FORMS_URL}/current",
        params={"scope_kind": "global"},
        headers=_headers(),
    )
    assert current.status_code == HTTPStatus.OK, current.text
    round_tripped_file = current.json()["fields"][1]
    assert round_tripped_file == fields[1]


def test_application_form_field_union_defaults_page_and_visible_when() -> None:
    """Risk annotation: group=TG-1;
    named_risk=visible_when_contract_roundtrip_and_publish_validator;
    level=contract;
    source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-1.
    """
    from pydantic import TypeAdapter

    from app.contracts.applications import ApplicationFormField

    adapter = TypeAdapter(ApplicationFormField)
    raw_fields: list[dict[str, Any]] = [
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
        {"id": "raid_count", "type": "number", "label": "Raid count"},
        {
            "id": "class",
            "type": "select",
            "label": "Class",
            "options": ["warrior", "mage"],
        },
        {
            "id": "roles",
            "type": "multi_select",
            "label": "Roles",
            "options": ["tank", "healer"],
        },
        {"id": "rules", "type": "boolean", "label": "Rules accepted"},
        {
            "id": "chapter",
            "type": "chapter_select",
            "label": "Chapter",
            "required": True,
            "placeholder": "Choose a chapter",
        },
    ]

    parsed = [adapter.validate_python(field) for field in raw_fields]

    assert [field.type for field in parsed] == [
        "short",
        "long",
        "number",
        "select",
        "multi_select",
        "boolean",
        "chapter_select",
    ]
    assert all(field.page == 1 for field in parsed)
    assert all(field.visible_when is None for field in parsed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "payload"),
    [
        pytest.param(
            "cycle_a_b_a",
            _global_conditional_payload(
                [
                    {
                        "id": "a",
                        "type": "short",
                        "label": "A",
                        "visible_when": {"field_id": "b", "op": "eq", "value": "yes"},
                    },
                    {
                        "id": "b",
                        "type": "short",
                        "label": "B",
                        "visible_when": {"field_id": "a", "op": "eq", "value": "yes"},
                    },
                ]
            ),
            id="cycle-a-b-a",
        ),
        pytest.param(
            "multi_select_source",
            _global_conditional_payload(
                [
                    {
                        "id": "roles",
                        "type": "multi_select",
                        "label": "Roles",
                        "options": ["tank", "healer"],
                    },
                    {
                        "id": "detail",
                        "type": "short",
                        "label": "Detail",
                        "visible_when": {
                            "field_id": "roles",
                            "op": "in",
                            "value": ["tank"],
                        },
                    },
                ]
            ),
            id="multi-select-source",
        ),
        pytest.param(
            "chapter_select_source",
            _global_chapter_conditional_payload(
                [
                    {
                        "id": "chapter",
                        "type": "chapter_select",
                        "label": "Chapter",
                        "required": True,
                    },
                    {
                        "id": "detail",
                        "type": "short",
                        "label": "Detail",
                        "visible_when": {
                            "field_id": "chapter",
                            "op": "eq",
                            "value": "chapter-alpha",
                        },
                    },
                ]
            ),
            id="chapter-select-source",
        ),
        pytest.param(
            "forward_reference",
            _global_conditional_payload(
                [
                    {"id": "a", "type": "short", "label": "A"},
                    {
                        "id": "b",
                        "type": "short",
                        "label": "B",
                        "visible_when": {"field_id": "c", "op": "eq", "value": "yes"},
                    },
                    {"id": "c", "type": "short", "label": "C"},
                ]
            ),
            id="forward-reference",
        ),
        pytest.param(
            "chapter_select_visible_when",
            _global_chapter_conditional_payload(
                [
                    {"id": "a", "type": "short", "label": "A"},
                    {
                        "id": "chapter",
                        "type": "chapter_select",
                        "label": "Chapter",
                        "required": True,
                        "visible_when": {"field_id": "a", "op": "eq", "value": "yes"},
                    },
                ]
            ),
            id="chapter-select-visible-when",
        ),
        pytest.param(
            "page_below_one",
            _global_conditional_payload(
                [
                    {
                        "id": "a",
                        "type": "short",
                        "label": "A",
                        "page": 0,
                    },
                ]
            ),
            id="page-below-one",
        ),
    ],
)
async def test_publish_form_rejects_visible_when_graph_violations(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    case_id: str,
    payload: dict[str, Any],
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=visible_when_contract_roundtrip_and_publish_validator;
    level=contract;
    source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)

    response = await migrated_async_client.post(
        FORMS_URL,
        json={**payload, "name": f"Invalid {case_id}"},
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_publish_form_with_chained_visible_when_round_trips(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=visible_when_contract_roundtrip_and_publish_validator;
    level=contract;
    source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-1.
    """
    _grant(governance_db)
    fields = [
        {"id": "a", "type": "short", "label": "A", "page": 1},
        {
            "id": "b",
            "type": "short",
            "label": "B",
            "page": 2,
            "visible_when": {"field_id": "a", "op": "eq", "value": "yes"},
        },
        {
            "id": "c",
            "type": "short",
            "label": "C",
            "page": 3,
            "visible_when": {"field_id": "b", "op": "eq", "value": "value"},
        },
    ]

    response = await migrated_async_client.post(
        FORMS_URL,
        json=_global_conditional_payload(fields),
        headers=_headers(**{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert [field["visible_when"] for field in response.json()["fields"][1:]] == [
        fields[1]["visible_when"],
        fields[2]["visible_when"],
    ]


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
    responses = {
        "short_answer": "Kalec",
        "long_answer": "I want to join scheduled guild activities.",
        "raid_count": 3,
        "class": "mage",
        "roles": ["damage"],
        "rules": True,
        "chapter": "chapter-1",
    }

    _validate_application_responses_impl(
        reparsed_fields,
        responses,
        file_upload_service=object(),  # no file fields in this fixture
        public_chapters_repo=object(),  # connection=None preserves pure validation
    )

    assert responses == {
        "short_answer": "Kalec",
        "long_answer": "I want to join scheduled guild activities.",
        "raid_count": 3,
        "class": "mage",
        "roles": ["damage"],
        "rules": True,
        "chapter": "chapter-1",
    }
    assert isinstance(responses["chapter"], str)
    assert isinstance(responses["short_answer"], str)
    assert isinstance(responses["long_answer"], str)
    assert isinstance(responses["raid_count"], int | float)
    assert not isinstance(responses["raid_count"], bool)
    assert isinstance(responses["rules"], bool)
    assert isinstance(responses["class"], str)
    assert responses["roles"] == ["damage"]
    assert all(isinstance(role, str) for role in responses["roles"])
