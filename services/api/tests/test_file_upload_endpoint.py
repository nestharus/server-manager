from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
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
def allowed_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    app.state.cedar_authorizer = authorizer
    return authorizer


@pytest.fixture()
def denied_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Deny")
    app.state.cedar_authorizer = authorizer
    return authorizer


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


def _patch_presigned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    file_upload = importlib.import_module("app.services.file_upload")

    def fake_generate_presigned_put_url(
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

    monkeypatch.setattr(
        file_upload,
        "generate_presigned_put_url",
        fake_generate_presigned_put_url,
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2.
    """
    form_id = seed_global_file_field_form(governance_db)
    _patch_presigned_url(monkeypatch)

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=upload_url_receipt_required_and_strict_validation_and_signed_params;
    level=component;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-2-F2.
    """
    form_id = seed_global_file_field_form(governance_db)
    file_upload = importlib.import_module("app.services.file_upload")
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

    monkeypatch.setattr(
        file_upload,
        "build_s3_client",
        lambda *args, **kwargs: FakeS3Client(),
        raising=False,
    )
    if hasattr(file_upload, "boto3"):
        monkeypatch.setattr(
            file_upload.boto3,
            "client",
            lambda *args, **kwargs: FakeS3Client(),
        )

    response = await _post_upload_url(
        migrated_async_client,
        body=_valid_body(str(form_id)),
        receipt=applicant_receipt_token(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert captured["ClientMethod"] == "put_object"
    assert captured["Params"]["ContentType"] == "image/png"
    assert captured["Params"]["ContentLength"] == 1024
