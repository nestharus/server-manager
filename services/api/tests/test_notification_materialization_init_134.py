from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase

from .public_intake_fixtures import assert_risk_annotation
from .test_notification_materialization import (
    _insert_event,
    _insert_rule,
    _load_materialize_event,
)


APPLICATION_EVENT_TYPE = "application.public_submitted"
OFFICER_CHANNEL_ID = "222222222222222222"
APPLICATION_MANAGERS_ROLE_ID = "333333333333333333"
APPLICANT_DISCORD_USER_ID = "123456789012345678"
PRIMARY_GUILD_CHANNEL_URL = (
    "https://discord.com/channels/111111111111111111/222222222222222222"
)


def _assert_tg2() -> None:
    assert_risk_annotation(
        group="TG-2",
        named_risk="init_134_notification_materialization_contract",
        level="component",
        source=".tmp/init-134/phase6/step6a-contract.md#TG-2",
    )


def _application_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "application_id": "12345678-1234-5678-1234-567812345678",
        "support_id": "APP-12345678",
        "recipient_discord_user_id": APPLICANT_DISCORD_USER_ID,
        "scope_kind": "global",
        "scope_id": None,
        "scope_label": "Global",
        "submitted_unix_ts": "1777487400",
        "submitted_iso": "2026-04-29T18:30:00+00:00",
        "form_version": "1",
        "character_name": "Test Applicant",
        "response_preview": "I want to join scheduled guild activities.",
        "application_url": (
            "https://web.test.humility.local/applications/"
            "12345678-1234-5678-1234-567812345678"
        ),
        "officer_review_channel_id": OFFICER_CHANNEL_ID,
        "application_managers_role_id": APPLICATION_MANAGERS_ROLE_ID,
        "application_managers_role_mention": f"<@&{APPLICATION_MANAGERS_ROLE_ID}>",
        "primary_guild_channel_url": PRIMARY_GUILD_CHANNEL_URL,
    }
    payload.update(overrides)
    return payload


def _officer_recipients() -> dict[str, Any]:
    return {
        "kind": "event_payload_designated_channel",
        "channel_id_payload_key": "officer_review_channel_id",
        "role_id_payload_key": "application_managers_role_id",
    }


def _applicant_recipients() -> dict[str, Any]:
    return {
        "kind": "event_payload_discord_user",
        "user_id_payload_key": "recipient_discord_user_id",
    }


def _officer_template() -> dict[str, Any]:
    return {
        "title": "",
        "body": "${payload_application_managers_role_mention}",
        "embed": {
            "title": "New application submission - ${payload_scope_label}",
            "description": "${payload_response_preview}",
            "url": "${payload_application_url}",
            "color": 3447003,
            "fields": [
                {"name": "Application ID", "value": "${payload_application_id}", "inline": False},
                {"name": "Scope", "value": "${payload_scope_label}", "inline": True},
                {"name": "Submitted", "value": "<t:${payload_submitted_unix_ts}:R>", "inline": True},
                {"name": "Form version", "value": "${payload_form_version}", "inline": True},
                {"name": "Support ID", "value": "${payload_support_id}", "inline": True},
                {"name": "Character", "value": "${payload_character_name}", "inline": True},
            ],
        },
    }


def _applicant_template() -> dict[str, Any]:
    return {
        "title": "",
        "body": (
            "Application received. Keep an eye on "
            "${payload_primary_guild_channel_url} for next steps."
        ),
    }


def _fetch_envelopes_with_embed(
    dsn: str,
    *,
    source_event_id: UUID,
) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, rule_id, source_event_id, recipient_key,
                       recipient_discord_id, recipient_display, channel,
                       destination_channel_id, rendered_body,
                       rendered_embed_json, delivery_status, last_error_json
                FROM notification_envelopes
                WHERE source_event_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (source_event_id,),
            ).fetchall()
        ]


def test_officer_rule_renders_designated_channel_envelope_with_embed(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_officer_recipients(),
        channel="designated_channel",
        template_json=_officer_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["channel"] == "designated_channel"
    assert envelope["destination_channel_id"] == OFFICER_CHANNEL_ID
    assert envelope["recipient_key"] == f"discord_role:{APPLICATION_MANAGERS_ROLE_ID}"
    assert envelope["rendered_body"] == f"<@&{APPLICATION_MANAGERS_ROLE_ID}>"
    assert envelope["delivery_status"] == "pending"
    assert envelope["rendered_embed_json"]["title"] == "New application submission - Global"
    assert envelope["rendered_embed_json"]["url"].endswith(
        "/applications/12345678-1234-5678-1234-567812345678"
    )
    assert envelope["rendered_embed_json"]["fields"][0] == {
        "name": "Application ID",
        "value": "12345678-1234-5678-1234-567812345678",
        "inline": False,
    }


def test_applicant_rule_renders_dm_envelope(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_applicant_recipients(),
        channel="dm",
        template_json=_applicant_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    envelopes = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["channel"] == "dm"
    assert envelope["recipient_key"] == f"discord_user:{APPLICANT_DISCORD_USER_ID}"
    assert envelope["recipient_discord_id"] == APPLICANT_DISCORD_USER_ID
    assert envelope["destination_channel_id"] is None
    assert envelope["rendered_embed_json"] is None
    assert PRIMARY_GUILD_CHANNEL_URL in envelope["rendered_body"]
    assert envelope["delivery_status"] == "pending"


def test_missing_channel_id_skips_officer_envelope_with_reason(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_officer_recipients(),
        channel="designated_channel",
        template_json=_officer_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(officer_review_channel_id=None),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    envelope = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)[0]
    assert envelope["delivery_status"] == "skipped"
    assert envelope["last_error_json"]["reason"] == "destination_missing"


def test_missing_role_id_skips_officer_envelope_with_reason(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_officer_recipients(),
        channel="designated_channel",
        template_json=_officer_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(application_managers_role_id=None),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    envelope = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)[0]
    assert envelope["delivery_status"] == "skipped"
    assert envelope["last_error_json"]["reason"] == "recipient_unresolved"


def test_missing_guild_url_skips_applicant_envelope_with_reason(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_applicant_recipients(),
        channel="dm",
        template_json=_applicant_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(primary_guild_channel_url=None),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    envelope = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)[0]
    assert envelope["delivery_status"] == "skipped"
    assert envelope["last_error_json"]["reason"] != "template_missing_key"
    assert "primary_guild_channel_url" in envelope["last_error_json"]["reason"]


def test_embed_non_string_fields_pass_through_unchanged(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_officer_recipients(),
        channel="designated_channel",
        template_json=_officer_template(),
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    embed = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)[0][
        "rendered_embed_json"
    ]
    assert embed["color"] == 3447003
    assert isinstance(embed["color"], int)
    assert embed["fields"][0]["inline"] is False
    assert embed["fields"][1]["inline"] is True


def test_template_substitution_applied_only_to_string_fields(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    _assert_tg2()
    materialize_event = _load_materialize_event()
    template = _officer_template()
    template["embed"]["color"] = 11259375
    template["embed"]["fields"] = [
        {"name": "Scope ${payload_scope_label}", "value": "${payload_scope_kind}", "inline": True},
        {"name": "Static", "value": "Value", "inline": False},
    ]
    _insert_rule(
        governance_dsn,
        trigger_json={"event_type": APPLICATION_EVENT_TYPE},
        recipients_json=_officer_recipients(),
        channel="designated_channel",
        template_json=template,
    )
    event_id = _insert_event(
        governance_dsn,
        event_type=APPLICATION_EVENT_TYPE,
        payload_json=_application_payload(),
        scope_kind="global",
        scope_id=None,
    )

    materialize_event(governance_db, event_id, worker_id="notification-dispatcher")

    embed = _fetch_envelopes_with_embed(governance_dsn, source_event_id=event_id)[0][
        "rendered_embed_json"
    ]
    assert embed["title"] == "New application submission - Global"
    assert embed["description"] == "I want to join scheduled guild activities."
    assert embed["fields"][0] == {
        "name": "Scope Global",
        "value": "global",
        "inline": True,
    }
    assert embed["color"] == 11259375
    assert isinstance(embed["color"], int)
