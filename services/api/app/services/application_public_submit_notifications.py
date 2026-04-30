from __future__ import annotations

import re
from typing import Any

from app.contracts.applications import ApplicationRead


APPLICATION_PREVIEW_MAX_CHARS = 200
APPLICATION_TEXT_FIELD_ID = "application_text"
CHARACTER_NAME_FIELD_ID = "character_name"
APPLICATION_REVIEW_CHANNEL_KEY = "applications_review"
APPLICATION_MANAGERS_ROLE_KEY = "application_managers"


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate_preview(value: str) -> str:
    if len(value) <= APPLICATION_PREVIEW_MAX_CHARS:
        return value
    return value[:APPLICATION_PREVIEW_MAX_CHARS] + "..."


def _response_preview(responses: dict[str, Any]) -> str:
    preferred = _as_str(responses.get(APPLICATION_TEXT_FIELD_ID))
    if preferred is not None:
        return _truncate_preview(_collapse_whitespace(preferred))
    # Application responses preserve form field insertion order; after the
    # preferred application text field, use the first normalized non-empty value.
    for raw_value in responses.values():
        fallback = _as_str(raw_value)
        if fallback is not None:
            return _truncate_preview(_collapse_whitespace(fallback))
    return ""


def _character_name(responses: dict[str, Any]) -> str:
    return _collapse_whitespace(_as_str(responses.get(CHARACTER_NAME_FIELD_ID)) or "")


def _support_id(application: ApplicationRead) -> str:
    return f"APP-{str(application.id).split('-', maxsplit=1)[0]}"


def _scope_label(scope_kind: str, scope_id: str | None) -> str:
    if scope_kind == "global":
        return "Global"
    if scope_id:
        return f"{scope_kind.title()} {scope_id}"
    return scope_kind.title()


def _resource_map_value(
    resources: dict[str, Any] | Any | None,
    *,
    group_key: str,
    item_key: str,
) -> str | None:
    if resources is None:
        return None
    if isinstance(resources, dict):
        group = resources.get(group_key, {})
    else:
        group = getattr(resources, group_key, {})
    if not isinstance(group, dict):
        return None
    return _as_str(group.get(item_key))


def build_officer_payload(
    *,
    scope_kind: str,
    scope_id: str | None,
    global_applications_review_channel_id: str | None,
    global_application_managers_role_id: str | None,
    chapter_discord_resources: dict[str, Any] | Any | None,
) -> dict[str, Any] | None:
    if scope_kind == "chapter":
        review_channel_id = _resource_map_value(
            chapter_discord_resources,
            group_key="channel_ids",
            item_key=APPLICATION_REVIEW_CHANNEL_KEY,
        )
        managers_role_id = _resource_map_value(
            chapter_discord_resources,
            group_key="role_ids",
            item_key=APPLICATION_MANAGERS_ROLE_KEY,
        )
    else:
        review_channel_id = _as_str(global_applications_review_channel_id)
        managers_role_id = _as_str(global_application_managers_role_id)

    if review_channel_id is None or managers_role_id is None:
        return None
    return {
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "officer_review_channel_id": review_channel_id,
        "application_managers_role_id": managers_role_id,
        "application_managers_role_mention": f"<@&{managers_role_id}>",
    }


def build_applicant_payload(
    *,
    recipient_discord_user_id: str,
    global_primary_guild_channel_url: str | None,
) -> dict[str, str] | None:
    recipient_id = _as_str(recipient_discord_user_id)
    guild_channel_url = _as_str(global_primary_guild_channel_url)
    if recipient_id is None or guild_channel_url is None:
        return None
    return {
        "recipient_discord_user_id": recipient_id,
        "primary_guild_channel_url": guild_channel_url,
    }


def build_application_public_submit_payload(
    *,
    application: ApplicationRead,
    recipient_discord_user_id: str,
    web_public_base_url: str,
    global_applications_review_channel_id: str | None,
    global_application_managers_role_id: str | None,
    global_primary_guild_channel_url: str | None,
    chapter_discord_resources: dict[str, Any] | Any | None = None,
) -> dict[str, Any] | None:
    scope_kind = str(application.target_scope.scope_kind)
    scope_id = application.target_scope.scope_id
    officer_payload = build_officer_payload(
        scope_kind=scope_kind,
        scope_id=scope_id,
        global_applications_review_channel_id=global_applications_review_channel_id,
        global_application_managers_role_id=global_application_managers_role_id,
        chapter_discord_resources=chapter_discord_resources,
    )
    applicant_payload = build_applicant_payload(
        recipient_discord_user_id=recipient_discord_user_id,
        global_primary_guild_channel_url=global_primary_guild_channel_url,
    )
    if officer_payload is None or applicant_payload is None:
        return None

    base_url = web_public_base_url.rstrip("/")
    return {
        "application_id": str(application.id),
        "support_id": _support_id(application),
        "recipient_discord_user_id": applicant_payload["recipient_discord_user_id"],
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "scope_label": _scope_label(scope_kind, scope_id),
        "submitted_unix_ts": str(int(application.submitted_at.timestamp())),
        "submitted_iso": application.submitted_at.isoformat(),
        "form_version": str(application.form_version),
        "character_name": _character_name(application.responses),
        "response_preview": _response_preview(application.responses),
        "application_url": f"{base_url}/applications/{application.id}",
        "officer_review_channel_id": officer_payload["officer_review_channel_id"],
        "application_managers_role_id": officer_payload["application_managers_role_id"],
        "application_managers_role_mention": officer_payload[
            "application_managers_role_mention"
        ],
        "primary_guild_channel_url": applicant_payload["primary_guild_channel_url"],
    }
