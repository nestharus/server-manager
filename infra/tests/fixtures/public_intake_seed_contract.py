from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4


SEED_MANIFEST_RELATIVE_PATH = Path(
    "gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml"
)
SEED_CONFIGMAP_NAME = "seed-public-intake-form-payload"
SEED_JOB_NAME = "seed-public-intake-form"
SEED_AGGREGATE_ID = "application_form|global|"
SEED_ACTOR_KIND = "service"
SEED_ACTOR_ID = "init-122-bootstrap"
SEED_REQUEST_SURFACE = "kubernetes:job/seed-public-intake-form"
SEED_FORM_NAME = "Public application intake (global)"
SEED_TARGET_TYPE = "chapter_membership"
SEED_SOURCE = "proposals/04-public-intake-form-seed.md#test-intent-track"


@dataclass(frozen=True)
class SeedSqlRun:
    notices: tuple[str, ...]
    rows: tuple[dict[str, object], ...]


def deterministic_public_intake_seed_form_id() -> UUID:
    seed_hex = hashlib.sha256(b"init-122:public-intake-global:v1").hexdigest()[:32]
    return UUID(hex=seed_hex)


def assert_init122_risk_annotation(
    *,
    group: str,
    named_risk: str,
    level: str,
    source: str,
) -> None:
    assert group in {"TG-1", "TG-2", "TG-3", "TG-4", "TG-5"}
    assert named_risk
    assert level in {"component", "particular-integration", "end-to-end"}
    assert source


def fetch_public_intake_seed_rows(database_url: str) -> dict[str, list[dict]]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        form_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, scope_kind, scope_id, status, version, target_type, name,
                       fields, routing_rules, published_by_kind, published_by_id
                FROM form_definitions
                WHERE scope_kind = 'global'
                  AND scope_id IS NULL
                  AND status = 'current'
                ORDER BY id
                """
            ).fetchall()
        ]
        action_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, aggregate_id, action_type, actor_kind, actor_id, status,
                       request_surface
                FROM activity_actions
                WHERE aggregate_type = 'application_form'
                  AND aggregate_id = %s
                ORDER BY id
                """,
                (SEED_AGGREGATE_ID,),
            ).fetchall()
        ]
        state_change_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, action_id, aggregate_id, aggregate_seq, change_type
                FROM activity_state_changes
                WHERE aggregate_type = 'application_form'
                  AND aggregate_id = %s
                ORDER BY id
                """,
                (SEED_AGGREGATE_ID,),
            ).fetchall()
        ]
        head_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT aggregate_id, current_seq, latest_change_id
                FROM aggregate_heads
                WHERE aggregate_type = 'application_form'
                  AND aggregate_id = %s
                """,
                (SEED_AGGREGATE_ID,),
            ).fetchall()
        ]
    return {
        "forms": form_rows,
        "actions": action_rows,
        "state_changes": state_change_rows,
        "heads": head_rows,
    }


def insert_officer_current_global_form(database_url: str) -> UUID:
    import psycopg
    from psycopg.types.json import Jsonb

    form_id = uuid4()
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            INSERT INTO form_definitions (
                id, scope_kind, scope_id, version, name, target_type, fields,
                routing_rules, status, published_by_kind, published_by_id
            )
            VALUES (
                %s, 'global', NULL, 1, 'Officer published global form',
                'chapter_membership', %s, %s, 'current', 'user', 'officer-1'
            )
            """,
            (
                form_id,
                Jsonb(
                    [
                        {
                            "id": "officer_field",
                            "label": "Officer field",
                            "type": "short",
                            "required": True,
                        }
                    ]
                ),
                Jsonb({}),
            ),
        )
    return form_id
