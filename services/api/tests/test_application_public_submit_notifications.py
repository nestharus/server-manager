from __future__ import annotations

import importlib
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contracts.applications import ApplicationRead, PublicApplicationSubmission
from app.repositories.db import PostgresDatabase

from .public_intake_fixtures import (
    APPLICANT_DISCORD_USER_ID,
    applicant_receipt_token,
    assert_risk_annotation,
    fetch_application_by_client_id,
    fetch_application_row,
    fetch_public_submitted_events,
    public_application_payload,
    seed_global_public_application_form,
)
from .test_public_application_route import FakeCedarAuthorizer


pytestmark = pytest.mark.asyncio

WEB_PUBLIC_BASE_URL = "https://web.test.humility.local"
GLOBAL_REVIEW_CHANNEL_ID = "222222222222222222"
GLOBAL_APPLICATION_MANAGERS_ROLE_ID = "333333333333333333"
GLOBAL_PRIMARY_GUILD_CHANNEL_URL = (
    "https://discord.com/channels/111111111111111111/222222222222222222"
)


def _load_builder() -> Any:
    try:
        module = importlib.import_module(
            "app.services.application_public_submit_notifications"
        )
    except ModuleNotFoundError as error:
        pytest.fail(f"missing INIT-134 public-submit notification builder: {error}")
    builder = getattr(module, "build_application_public_submit_payload", None)
    if builder is None:
        pytest.fail("missing build_application_public_submit_payload(...) helper")
    return builder


def _application_read(
    *,
    application_id: UUID | None = None,
    scope_kind: str = "global",
    scope_id: str | None = None,
    responses: dict[str, Any] | None = None,
    submitted_at: datetime | None = None,
) -> ApplicationRead:
    now = submitted_at or datetime(2026, 4, 29, 18, 30, 0, tzinfo=UTC)
    return ApplicationRead(
        id=application_id or uuid4(),
        applicant_id=uuid4(),
        form_definition_id=uuid4(),
        form_version=1,
        form_snapshot={"name": "Public Application"},
        target_scope={"scope_kind": scope_kind, "scope_id": scope_id},
        responses=responses
        or {
            "character_name": "Test Applicant",
            "application_text": "I want to join scheduled guild activities.",
        },
        state="queued",
        submitted_at=now,
        queued_at=now,
        created_at=now,
        updated_at=now,
        version=2,
    )


def _builder_kwargs(
    *,
    application: ApplicationRead | None = None,
    recipient_discord_user_id: str = APPLICANT_DISCORD_USER_ID,
    web_public_base_url: str = WEB_PUBLIC_BASE_URL,
    global_applications_review_channel_id: str | None = GLOBAL_REVIEW_CHANNEL_ID,
    global_application_managers_role_id: str | None = GLOBAL_APPLICATION_MANAGERS_ROLE_ID,
    global_primary_guild_channel_url: str | None = GLOBAL_PRIMARY_GUILD_CHANNEL_URL,
    chapter_discord_resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "application": application or _application_read(),
        "recipient_discord_user_id": recipient_discord_user_id,
        "web_public_base_url": web_public_base_url,
        "global_applications_review_channel_id": global_applications_review_channel_id,
        "global_application_managers_role_id": global_application_managers_role_id,
        "global_primary_guild_channel_url": global_primary_guild_channel_url,
        "chapter_discord_resources": chapter_discord_resources,
    }


def _build_payload(**overrides: Any) -> dict[str, Any] | None:
    builder = _load_builder()
    kwargs = _builder_kwargs(**overrides)
    return builder(**kwargs)


def _assert_tg1_unit() -> None:
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_submit_notification_payload_contract",
        level="unit",
        source=".tmp/init-134/phase6/step6a-contract.md#TG-1",
    )


def _assert_tg1_component() -> None:
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_submit_notification_emit_contract",
        level="component",
        source=".tmp/init-134/phase6/step6a-contract.md#TG-1",
    )


@pytest.fixture()
def public_form(governance_db: PostgresDatabase) -> None:
    seed_global_public_application_form(governance_db)


@pytest.fixture()
def allowed_public_route(app: FastAPI) -> FakeCedarAuthorizer:
    authorizer = FakeCedarAuthorizer(decision="Allow")
    app.state.cedar_authorizer = authorizer
    return authorizer


async def _post_public_application(
    client: AsyncClient,
    *,
    client_application_id: str,
    responses: dict[str, Any] | None = None,
):
    payload = public_application_payload(client_application_id=client_application_id)
    if responses is not None:
        payload["responses"] = responses
    return await client.post(
        "/api/v1/public/applications",
        json=payload,
        cookies={"applicant_receipt": applicant_receipt_token()},
    )


def test_payload_builds_with_all_fields_present() -> None:
    _assert_tg1_unit()

    application = _application_read()
    payload = _build_payload(application=application)

    assert payload is not None
    assert payload == {
        "application_id": str(application.id),
        "support_id": payload["support_id"],
        "recipient_discord_user_id": APPLICANT_DISCORD_USER_ID,
        "scope_kind": "global",
        "scope_id": None,
        "scope_label": "Global",
        "submitted_unix_ts": str(int(application.submitted_at.timestamp())),
        "submitted_iso": application.submitted_at.isoformat(),
        "form_version": "1",
        "character_name": "Test Applicant",
        "response_preview": "I want to join scheduled guild activities.",
        "application_url": f"{WEB_PUBLIC_BASE_URL}/applications/{application.id}",
        "officer_review_channel_id": GLOBAL_REVIEW_CHANNEL_ID,
        "application_managers_role_id": GLOBAL_APPLICATION_MANAGERS_ROLE_ID,
        "application_managers_role_mention": f"<@&{GLOBAL_APPLICATION_MANAGERS_ROLE_ID}>",
        "primary_guild_channel_url": GLOBAL_PRIMARY_GUILD_CHANNEL_URL,
    }
    assert payload["support_id"]


def test_payload_truncates_application_text_at_200_chars() -> None:
    _assert_tg1_unit()
    application = _application_read(
        responses={"character_name": "Test Applicant", "application_text": "a" * 201}
    )

    payload = _build_payload(application=application)

    assert payload is not None
    assert payload["response_preview"] == ("a" * 200) + "..."


def test_payload_collapses_newlines_to_spaces() -> None:
    _assert_tg1_unit()
    application = _application_read(
        responses={
            "character_name": "Test Applicant",
            "application_text": "Line one\n\nLine\t two   line three",
        }
    )

    payload = _build_payload(application=application)

    assert payload is not None
    assert payload["response_preview"] == "Line one Line two line three"


def test_payload_uses_first_non_empty_response_when_application_text_missing() -> None:
    _assert_tg1_unit()
    application = _application_read(
        responses={
            "first_empty": "   ",
            "first_answer": "This should become the preview.",
            "second_answer": "This should not be used.",
        }
    )

    payload = _build_payload(application=application)

    assert payload is not None
    assert payload["response_preview"] == "This should become the preview."


def test_payload_excludes_member_uuid_email_username() -> None:
    _assert_tg1_unit()
    application = _application_read(
        responses={
            "character_name": "Test Applicant",
            "application_text": "Safe preview",
            "email": "applicant@example.com",
            "discord_username": "Applicant#0001",
            "applicant_member_id": str(uuid4()),
        }
    )

    payload = _build_payload(application=application)

    assert payload is not None
    encoded = repr(payload)
    assert "applicant@example.com" not in encoded
    assert "Applicant#0001" not in encoded
    assert str(application.applicant_id) not in encoded
    assert "applicant_member_id" not in payload
    assert "discord_user_id" not in payload
    assert "responses" not in payload


def test_payload_includes_application_id() -> None:
    _assert_tg1_unit()
    application = _application_read(application_id=UUID("12345678-1234-5678-1234-567812345678"))

    payload = _build_payload(application=application)

    assert payload is not None
    assert payload["application_id"] == "12345678-1234-5678-1234-567812345678"


def test_payload_constructs_url_from_web_public_base_url() -> None:
    _assert_tg1_unit()
    application = _application_read()

    payload = _build_payload(
        application=application,
        web_public_base_url="https://review.example.test/",
    )

    assert payload is not None
    assert payload["application_url"] == (
        f"https://review.example.test/applications/{application.id}"
    )


def test_payload_handles_global_scope_with_global_config() -> None:
    _assert_tg1_unit()

    payload = _build_payload(application=_application_read(scope_kind="global", scope_id=None))

    assert payload is not None
    assert payload["scope_kind"] == "global"
    assert payload["scope_id"] is None
    assert payload["scope_label"] == "Global"
    assert payload["officer_review_channel_id"] == GLOBAL_REVIEW_CHANNEL_ID
    assert payload["application_managers_role_id"] == GLOBAL_APPLICATION_MANAGERS_ROLE_ID
    assert payload["primary_guild_channel_url"] == GLOBAL_PRIMARY_GUILD_CHANNEL_URL


def test_payload_handles_global_scope_without_global_config() -> None:
    _assert_tg1_unit()

    payload = _build_payload(
        application=_application_read(scope_kind="global", scope_id=None),
        global_applications_review_channel_id=None,
        global_application_managers_role_id=None,
        global_primary_guild_channel_url=None,
    )

    assert payload is None


def test_payload_handles_chapter_without_discord_config() -> None:
    _assert_tg1_unit()

    payload = _build_payload(
        application=_application_read(scope_kind="chapter", scope_id="chapter-one"),
        chapter_discord_resources=None,
    )

    assert payload is None


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_submit_emits_application_public_submitted_event(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
) -> None:
    _assert_tg1_component()

    response = await _post_public_application(
        migrated_async_client,
        client_application_id="init-134-event",
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = UUID(response.json()["application_id"])
    events = fetch_public_submitted_events(governance_dsn, application_id=application_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "application.public_submitted"


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_submit_emits_with_recipient_discord_user_id_from_receipt(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
) -> None:
    _assert_tg1_component()

    response = await _post_public_application(
        migrated_async_client,
        client_application_id="init-134-recipient",
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = UUID(response.json()["application_id"])
    payload = fetch_public_submitted_events(governance_dsn, application_id=application_id)[0][
        "payload_json"
    ]
    assert payload["recipient_discord_user_id"] == APPLICANT_DISCORD_USER_ID
    assert "discord_user_id" not in payload


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_submit_does_not_5xx_when_emit_raises(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_tg1_component()
    applications_module = importlib.import_module("app.services.applications")

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("notification emit unavailable")

    monkeypatch.setattr(applications_module, "emit_application_public_submitted_event", boom)

    response = await _post_public_application(
        migrated_async_client,
        client_application_id="init-134-emit-raises",
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = UUID(response.json()["application_id"])
    assert fetch_application_row(governance_dsn, application_id)["id"] == application_id


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_submit_payload_excludes_full_response_text(
    migrated_async_client: AsyncClient,
    governance_dsn: str,
) -> None:
    _assert_tg1_component()
    full_response = "private response body " * 80

    response = await _post_public_application(
        migrated_async_client,
        client_application_id="init-134-redaction",
        responses={"character_name": "Test Applicant", "application_text": full_response},
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    application_id = UUID(response.json()["application_id"])
    payload = fetch_public_submitted_events(governance_dsn, application_id=application_id)[0][
        "payload_json"
    ]
    assert "responses" not in payload
    assert full_response not in repr(payload)
    assert payload["response_preview"] != full_response
    assert len(payload["response_preview"]) <= 203


@pytest.mark.usefixtures("public_form", "allowed_public_route")
async def test_submit_idempotent_emit_via_event_key(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg1_component()
    service = importlib.import_module("app.services.applications").submit_public_application_with_receipt
    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="init-134-idempotent")
    )

    first_application_id = await service(
        governance_db,
        submission,
        discord_user_id=APPLICANT_DISCORD_USER_ID,
    )
    second_application_id = await service(
        governance_db,
        submission,
        discord_user_id=APPLICANT_DISCORD_USER_ID,
    )

    assert second_application_id == first_application_id
    assert fetch_application_by_client_id(governance_dsn, "init-134-idempotent")["id"] == first_application_id
    assert len(fetch_public_submitted_events(governance_dsn, application_id=first_application_id)) == 1
