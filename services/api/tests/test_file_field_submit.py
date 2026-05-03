from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from dependency_injector import providers
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.contracts.applications import InvalidApplicationResponseError
from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .chapter_selector_fixtures import (
    chapter_selector_public_payload,
    seed_chapter,
)
from .file_upload_fixtures import (
    FILE_FIELD_ID,
    FILE_MAX_SIZE_BYTES,
    boolean_field,
    fetch_application_response_row,
    file_field,
    file_object_key,
    file_response,
    long_text_field,
    seed_global_chapter_selector_file_form,
    seed_global_file_field_form,
    text_field,
)
from .public_intake_fixtures import applicant_receipt_token


pytestmark = pytest.mark.asyncio

PUBLIC_SUBMIT_URL = "/api/v1/public/applications"


@dataclass
class FakeCedarAuthorizer:
    decision: str = "Allow"
    requests: list[CedarAuthorizationRequest] = field(default_factory=list)

    def is_authorized(self, request: CedarAuthorizationRequest) -> CedarAuthorizationDecision:
        self.requests.append(request)
        return CedarAuthorizationDecision(decision=self.decision)


@pytest.fixture()
def allowed_public_route(app: FastAPI, override_provider) -> Iterator[FakeCedarAuthorizer]:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        yield authorizer


def _client_id(label: str) -> str:
    return f"init-137-{label}-{uuid4().hex}"


async def _post_public_application(
    client: AsyncClient,
    *,
    payload: dict[str, Any],
) -> Response:
    return await client.post(
        PUBLIC_SUBMIT_URL,
        json=payload,
        cookies={"applicant_receipt": applicant_receipt_token()},
    )


def _payload(
    *,
    responses: dict[str, Any],
    client_application_id: str,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "scope": scope or {"scope_kind": "global", "scope_id": None},
        "responses": responses,
        "client_application_id": client_application_id,
    }


def _base_responses(file_value: dict[str, Any] | None) -> dict[str, Any]:
    responses: dict[str, Any] = {
        "character_name": "Kalec",
        "application_text": "I want to join scheduled guild activities.",
    }
    if file_value is not None:
        responses[FILE_FIELD_ID] = file_value
    return responses


class FakeFileUploadService:
    def __init__(self, *, head) -> None:
        self._head = head

    def head_object(self, object_key: str) -> tuple[int, str]:
        return self._head(object_key)


def _patch_head_object(
    app: FastAPI,
    *,
    size_bytes: int = 1024,
    content_type: str = "image/png",
    missing: bool = False,
) -> None:
    def fake_head(object_key: str) -> tuple[int, str]:
        if missing:
            raise InvalidApplicationResponseError(f"missing upload object for {FILE_FIELD_ID}")
        assert object_key.startswith("applications/")
        return size_bytes, content_type

    app.state.container.services.file_upload.override(
        providers.Object(FakeFileUploadService(head=fake_head)),
    )


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_with_file_response_matching_s3_object_succeeds(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    application_id = uuid4()
    uploaded = file_response(application_id=application_id)
    _patch_head_object(app)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-happy"),
            responses=_base_responses(uploaded),
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert UUID(response.json()["application_id"]) == application_id
    row = fetch_application_response_row(governance_db, application_id)
    assert row["responses"][FILE_FIELD_ID] == uploaded


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_object_key_absent_in_s3_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app, missing=True)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-missing-s3"),
            responses=_base_responses(file_response()),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_s3_content_type_mismatch_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app, content_type="image/jpeg")

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-content-type-mismatch"),
            responses=_base_responses(file_response(content_type="image/png")),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_s3_size_mismatch_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app, size_bytes=2048)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-size-mismatch"),
            responses=_base_responses(file_response(size_bytes=1024)),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_file_response_content_type_not_in_accept_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app, content_type="image/jpeg")

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-accept-mismatch"),
            responses=_base_responses(
                file_response(content_type="image/jpeg", size_bytes=1024)
            ),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_file_response_size_above_max_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    oversized = FILE_MAX_SIZE_BYTES + 1
    _patch_head_object(app, size_bytes=oversized)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-oversized"),
            responses=_base_responses(file_response(size_bytes=oversized)),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_object_key_wrong_prefix_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-wrong-prefix"),
            responses=_base_responses(
                file_response(object_key=f"evil/{uuid4()}/{FILE_FIELD_ID}/{uuid4()}")
            ),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_object_key_wrong_field_id_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("file-wrong-field"),
            responses=_base_responses(
                file_response(object_key=file_object_key(field_id="other_file"))
            ),
        ),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_submit_file_response_extra_or_missing_keys_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app)
    malformed_values = [
        {**file_response(), "upload_url": "https://uploads.test.local/raw-url"},
        {"content_type": "image/png", "size_bytes": 1024},
        {"object_key": file_object_key(), "size_bytes": 1024},
        {"object_key": file_object_key(), "content_type": "image/png"},
    ]

    for index, value in enumerate(malformed_values):
        response = await _post_public_application(
            migrated_async_client,
            payload=_payload(
                client_application_id=_client_id(f"file-malformed-{index}"),
                responses=_base_responses(value),
            ),
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_hidden_file_field_does_not_require_upload_and_rejects_reference(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    fields = [
        text_field(),
        boolean_field(field_id="has_sheet", required=True),
        long_text_field(),
        file_field(
            required=True,
            visible_when={"field_id": "has_sheet", "op": "eq", "value": True},
        ),
    ]
    seed_global_file_field_form(governance_db, fields=fields)

    def fail_if_called(object_key: str) -> tuple[int, str]:
        raise AssertionError(f"hidden file field should not HEAD {object_key}")

    app.state.container.services.file_upload.override(
        providers.Object(FakeFileUploadService(head=fail_if_called)),
    )
    omitted_response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("hidden-file-omitted"),
            responses={
                "character_name": "Kalec",
                "has_sheet": False,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )
    hidden_value = file_response()
    rejected_response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("hidden-file-submitted"),
            responses={
                "character_name": "Kalec",
                "has_sheet": False,
                "application_text": "I want to join scheduled guild activities.",
                FILE_FIELD_ID: hidden_value,
            },
        ),
    )

    assert omitted_response.status_code == HTTPStatus.CREATED, omitted_response.text
    assert rejected_response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, rejected_response.text
    assert FILE_FIELD_ID in rejected_response.text
    assert hidden_value["object_key"] not in rejected_response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_file_field_on_global_form_without_chapter_selector_works(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_file_field_form(governance_db)
    _patch_head_object(app)

    response = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("global-file"),
            responses=_base_responses(file_response()),
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    row = fetch_application_response_row(
        governance_db,
        UUID(response.json()["application_id"]),
    )
    assert row["target_scope_kind"] == "global"
    assert row["target_scope_id"] is None


@pytest.mark.usefixtures("allowed_public_route")
async def test_existing_chapter_select_submit_path_still_works_with_file_form(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    seed_global_chapter_selector_file_form(governance_db)
    chapter_id = seed_chapter(governance_db, name="Alpha", state="active")

    response = await _post_public_application(
        migrated_async_client,
        payload=chapter_selector_public_payload(
            chapter_id=chapter_id,
            client_application_id=_client_id("chapter-selector-file-form"),
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    row = fetch_application_response_row(
        governance_db,
        UUID(response.json()["application_id"]),
    )
    assert row["target_scope_kind"] == "chapter"
    assert row["target_scope_id"] == chapter_id


@pytest.mark.usefixtures("allowed_public_route")
async def test_existing_visible_when_submit_paths_still_work_with_file_form(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3.
    """
    fields = [
        text_field(),
        boolean_field(field_id="wants_officer", label="Wants officer review"),
        {
            "id": "officer_statement",
            "type": "long",
            "label": "Officer statement",
            "required": True,
            "max_length": 4000,
            "visible_when": {
                "field_id": "wants_officer",
                "op": "eq",
                "value": True,
            },
        },
        long_text_field(),
        file_field(required=False),
    ]
    seed_global_file_field_form(governance_db, fields=fields)

    hidden_omitted = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("visible-when-hidden-omitted"),
            responses={
                "character_name": "Kalec",
                "wants_officer": False,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )
    visible_missing = await _post_public_application(
        migrated_async_client,
        payload=_payload(
            client_application_id=_client_id("visible-when-visible-missing"),
            responses={
                "character_name": "Kalec",
                "wants_officer": True,
                "application_text": "I want to join scheduled guild activities.",
            },
        ),
    )

    assert hidden_omitted.status_code == HTTPStatus.CREATED, hidden_omitted.text
    assert visible_missing.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, visible_missing.text


@pytest.mark.skip(reason="F3 stopgap pins beta-3 to one file field per form")
def test_submit_cross_field_application_id_disagreement_not_reachable_under_f3() -> None:
    """Risk annotation: group=TG-3;
    named_risk=submit_authoritative_head_verification_no_trust_the_spa;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-3-F3.
    """
