"""WU-045 application public-submit notifications."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_045_app_public_submit_notify"
down_revision = "wu_044_application_messages"
branch_labels = None
depends_on = None


OFFICER_RULE_ID = "c8c6e2f7-1f88-4a2f-9cf3-ef63dd7ab134"
APPLICANT_RULE_ID = "f46bd51e-6941-4e2f-8e68-0bf050d7b134"


def upgrade() -> None:
    op.add_column(
        "notification_envelopes",
        sa.Column(
            "rendered_embed_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    bind = op.get_bind()
    bind.exec_driver_sql(
        f"""
        INSERT INTO notification_rules (
            id,
            trigger_json,
            scope_kind,
            scope_id,
            recipients_json,
            channel,
            template_json,
            actionable,
            grouping,
            enabled
        )
        VALUES (
            '{OFFICER_RULE_ID}'::uuid,
            '{{"event_type": "application.public_submitted"}}'::jsonb,
            'global',
            NULL,
            '{{
              "kind": "event_payload_designated_channel",
              "channel_id_payload_key": "officer_review_channel_id",
              "role_id_payload_key": "application_managers_role_id"
            }}'::jsonb,
            'designated_channel',
            '{{
              "title": "",
              "body": "${{payload_application_managers_role_mention}}",
              "embed": {{
                "title": "New application submission - ${{payload_scope_label}}",
                "description": "${{payload_response_preview}}",
                "url": "${{payload_application_url}}",
                "color": 3447003,
                "fields": [
                  {{
                    "name": "Application ID",
                    "value": "${{payload_application_id}}",
                    "inline": false
                  }},
                  {{
                    "name": "Scope",
                    "value": "${{payload_scope_label}}",
                    "inline": true
                  }},
                  {{
                    "name": "Submitted",
                    "value": "<t:${{payload_submitted_unix_ts}}:R>",
                    "inline": true
                  }},
                  {{
                    "name": "Form version",
                    "value": "${{payload_form_version}}",
                    "inline": true
                  }},
                  {{
                    "name": "Support ID",
                    "value": "${{payload_support_id}}",
                    "inline": true
                  }},
                  {{
                    "name": "Character",
                    "value": "${{payload_character_name}}",
                    "inline": true
                  }}
                ]
              }}
            }}'::jsonb,
            FALSE,
            'per_event',
            TRUE
        ),
        (
            '{APPLICANT_RULE_ID}'::uuid,
            '{{"event_type": "application.public_submitted"}}'::jsonb,
            'global',
            NULL,
            '{{
              "kind": "event_payload_discord_user",
              "user_id_payload_key": "recipient_discord_user_id"
            }}'::jsonb,
            'dm',
            '{{
              "title": "",
              "body": "Application received. Keep an eye on ${{payload_primary_guild_channel_url}} for next steps."
            }}'::jsonb,
            FALSE,
            'per_event',
            TRUE
        )
        ON CONFLICT (id) DO NOTHING
        """
    )
    bind.exec_driver_sql(
        f"""
        INSERT INTO aggregate_heads (
            aggregate_type,
            aggregate_id,
            current_seq,
            latest_change_id
        )
        VALUES
            ('notification_rule', '{OFFICER_RULE_ID}', 1, NULL),
            ('notification_rule', '{APPLICANT_RULE_ID}', 1, NULL)
        ON CONFLICT (aggregate_type, aggregate_id) DO NOTHING
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        f"""
        DELETE FROM aggregate_heads
        WHERE aggregate_type = 'notification_rule'
          AND aggregate_id IN ('{OFFICER_RULE_ID}', '{APPLICANT_RULE_ID}')
        """
    )
    bind.exec_driver_sql(
        f"""
        DELETE FROM notification_rules
        WHERE id IN ('{OFFICER_RULE_ID}'::uuid, '{APPLICANT_RULE_ID}'::uuid)
        """
    )
    op.drop_column("notification_envelopes", "rendered_embed_json")
