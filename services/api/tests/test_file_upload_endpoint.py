from __future__ import annotations

from collections.abc import Iterator
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from dependency_injector import providers
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.contracts.authz import CedarAuthorizationDecision
from app.infrastructure.authz import CedarAuthorizationRequest
from app.repositories.db import PostgresDatabase

from .file_upload_fixtures import (
    FILE_FIELD_ID,
    FILE_MAX_SIZE_BYTES,
    seed_global_file_field_form,
)
from .public_intake_fixtures import applicant_receipt_token


pytestmark = pytest.mark.asyncio

UPLOAD_URL = "/api/v1/public/applications/upload-url"
OBJECT_KEY_PATTERN = re.compile(
    rf"^applications/[0-9a-f-]{{36}}/{FILE_FIELD_ID}/[0-9a-f-]{{36}}$"
)


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


@pytest.fixture()
def denied_public_route(app: FastAPI, override_provider) -> Iterator[FakeCedarAuthorizer]:
    authorizer = FakeCedarAuthorizer(decision="Deny")
    with override_provider(app.state.container.infra.cedar_authorizer, authorizer):
        yield authorizer


def _valid_body(form_id: str) -> dict[str, Any]:
    return {
        "form_definition_id": form_id,
        "field_id": FILE_FIELD_ID,
        "content_type": "image/png",
        "size_bytes": 1024,
    }


async def _post_upload_url(
    client: AsyncClient,
    *,
    body: dict[str, Any],
    receipt: str | None = None,
) -> Response:
    cookies = {"applicant_receipt": receipt or applicant_receipt_token()} if receipt is not None else {}
    return await client.post(UPLOAD_URL, json=body, cookies=cookies)


class FakeFileUploadService:
    def __init__(self, *, presign) -> None:
        self._presign = presign

    def validate_upload_request(
        self,
        *,
        fields,
        request,
        visibility,
    ):
        field = next((candidate for candidate in fields if candidate.id == request.field_id), None)
        assert field is not None
        assert visibility.get(request.field_id, False)
        assert request.content_type in field.accept
        assert 0 < request.size_bytes <= field.max_size_bytes
        return field, uuid4()

    def generate_presigned_put_url(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 600,
    ) -> tuple[str, datetime]:
        return self._presign(
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            expires_in_seconds=expires_in_seconds,
        )


def _patch_presigned_url(app: FastAPI) -> None:
    def fake_url(
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 600,
    ) -> tuple[str, datetime]:
        assert content_type == "image/png"
        assert size_bytes == 1024
        return (
            f"https://uploads.test.local/{object_key}",
            datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    app.state.container.services.file_upload.override(
        providers.Object(FakeFileUploadService(presign=fake_url)),
    )


@pytest.mark.usefixtures("allowed_public_route")
async def test_upload_url_receipt_required(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2.
    """
    form_id = seed_global_file_field_form(governance_db)

    response = await migrated_async_client.post(
        UPLOAD_URL,
        json=_valid_body(str(form_id)),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert response.json()["code"] == "applicant_receipt_required"


async def test_upload_url_public_intake_authority_required(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    denied_public_route: FakeCedarAuthorizer,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2.
    """
    form_id = seed_global_file_field_form(governance_db)

    response = await _post_upload_url(
        migrated_async_client,
        body=_valid_body(str(form_id)),
        receipt=applicant_receipt_token(),
    )

    assert denied_public_route.requests
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json() == {"detail": "public_intake_forbidden"}


@pytest.mark.usefixtures("allowed_public_route")
async def test_upload_url_accepts_content_type_in_field_accept_and_returns_contract_body(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2.
    """
    form_id = seed_global_file_field_form(governance_db)
    _patch_presigned_url(app)

    response = await _post_upload_url(
        migrated_async_client,
        body=_valid_body(str(form_id)),
        receipt=applicant_receipt_token(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert set(body) == {"upload_url", "object_key", "expires_at"}
    assert body["upload_url"].startswith("https://uploads.test.local/")
    assert OBJECT_KEY_PATTERN.fullmatch(body["object_key"])
    datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    serialized = response.text.lower()
    assert "s3_access_key_id" not in serialized
    assert "s3_secret_access_key" not in serialized
    assert "aws_access_key_id" not in serialized
    assert "aws_secret_access_key" not in serialized


@pytest.mark.usefixtures("allowed_public_route")
async def test_upload_url_rejects_content_type_not_in_accept(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2-F1.
    """
    form_id = seed_global_file_field_form(governance_db)
    body = {**_valid_body(str(form_id)), "content_type": "image/jpeg"}

    response = await _post_upload_url(
        migrated_async_client,
        body=body,
        receipt=applicant_receipt_token(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_upload_url_rejects_size_above_field_max(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2.
    """
    form_id = seed_global_file_field_form(governance_db)
    body = {**_valid_body(str(form_id)), "size_bytes": FILE_MAX_SIZE_BYTES + 1}

    response = await _post_upload_url(
        migrated_async_client,
        body=body,
        receipt=applicant_receipt_token(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.usefixtures("allowed_public_route")
async def test_upload_url_signed_params_include_content_length(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: FastAPI,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2-F2.
    """
    form_id = seed_global_file_field_form(governance_db)
    captured: dict[str, Any] = {}

    class FakeS3Client:
        def generate_presigned_url(
            self,
            ClientMethod: str,
            Params: dict[str, Any],
            ExpiresIn: int,
        ) -> str:
            captured["ClientMethod"] = ClientMethod
            captured["Params"] = Params
            captured["ExpiresIn"] = ExpiresIn
            return "https://uploads.test.local/presigned"

    app.state.container.infra.s3_client.override(providers.Object(FakeS3Client()))

    response = await _post_upload_url(
        migrated_async_client,
        body=_valid_body(str(form_id)),
        receipt=applicant_receipt_token(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert captured["ClientMethod"] == "put_object"
    assert captured["Params"]["ContentType"] == "image/png"
    assert captured["Params"]["ContentLength"] == 1024
