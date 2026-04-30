from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from .public_intake_fixtures import (
    APPLICANT_DISCORD_USER_ID,
    assert_risk_annotation,
    applicant_receipt_token,
    tamper_receipt_token,
)


@pytest.fixture()
def receipt_module():
    import importlib

    return importlib.import_module("app.services.applicant_discord_auth")


@pytest.fixture()
def receipt_dependency(receipt_module):
    return receipt_module.verify_applicant_receipt


@pytest.fixture()
def discord_identity_type(receipt_module):
    return receipt_module.DiscordIdentity


@pytest.fixture()
def valid_receipt() -> str:
    return applicant_receipt_token()


@pytest.fixture()
def tampered_receipt(valid_receipt: str) -> str:
    return tamper_receipt_token(valid_receipt)


@pytest.fixture()
def expired_receipt() -> str:
    return applicant_receipt_token(issued_at=datetime.now(UTC) - timedelta(seconds=601))


@pytest.fixture()
def wrong_key_receipt() -> str:
    return applicant_receipt_token(signing_key="wrong-test-signing-key-minimum-length")


def _request_with_cookie(receipt: str | None, settings) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if receipt is not None:
        headers.append((b"cookie", f"applicant_receipt={receipt}".encode("ascii")))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/public/applications",
        "headers": headers,
        "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
    }
    return Request(scope)


@pytest.fixture()
def valid_receipt_request(valid_receipt: str, test_settings) -> Request:
    return _request_with_cookie(valid_receipt, test_settings)


@pytest.fixture()
def missing_receipt_request(test_settings) -> Request:
    return _request_with_cookie(None, test_settings)


@pytest.fixture()
def tampered_receipt_request(tampered_receipt: str, test_settings) -> Request:
    return _request_with_cookie(tampered_receipt, test_settings)


@pytest.fixture()
def expired_receipt_request(expired_receipt: str, test_settings) -> Request:
    return _request_with_cookie(expired_receipt, test_settings)


@pytest.fixture()
def wrong_key_receipt_request(wrong_key_receipt: str, test_settings) -> Request:
    return _request_with_cookie(wrong_key_receipt, test_settings)


def _assert_receipt_required(error: HTTPException) -> None:
    assert error.status_code == 401
    assert isinstance(error.detail, dict)
    assert error.detail["code"] == "applicant_receipt_required"
    assert error.detail["message"]


def test_verify_applicant_receipt_returns_discord_identity(
    receipt_dependency,
    discord_identity_type,
    valid_receipt_request: Request,
) -> None:
    """Risk annotation: group=TG-1; named_risk=valid_receipt_identity_not_extracted;
    level=unit; source=.tmp/init-128/phase6/step6a-contract.md#C2.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="valid_receipt_identity_not_extracted",
        level="unit",
        source=".tmp/init-128/phase6/step6a-contract.md#C2",
    )

    identity = receipt_dependency(valid_receipt_request)

    assert isinstance(identity, discord_identity_type)
    assert identity.discord_user_id == APPLICANT_DISCORD_USER_ID


@pytest.mark.parametrize(
    "request_fixture",
    [
        pytest.param("missing_receipt_request", id="missing-cookie"),
        pytest.param("tampered_receipt_request", id="tampered-receipt"),
        pytest.param("expired_receipt_request", id="expired-receipt"),
        pytest.param("wrong_key_receipt_request", id="wrong-signing-key"),
    ],
)
def test_verify_applicant_receipt_rejects_missing_or_invalid_receipts(
    request: pytest.FixtureRequest,
    receipt_dependency,
    request_fixture: str,
) -> None:
    """Risk annotation: group=TG-1; named_risk=missing_or_invalid_receipt_accepted;
    level=unit; source=.tmp/init-128/phase6/step6a-contract.md#C2.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="missing_or_invalid_receipt_accepted",
        level="unit",
        source=".tmp/init-128/phase6/step6a-contract.md#C2",
    )
    receipt_request = request.getfixturevalue(request_fixture)

    with pytest.raises(HTTPException) as exc_info:
        receipt_dependency(receipt_request)

    _assert_receipt_required(exc_info.value)
