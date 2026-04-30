from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import yaml

from app.repositories.db import PostgresDatabase

from .chapter_selector_fixtures import (
    fetch_form_actions,
    fetch_form_aggregate_head,
    fetch_form_state_changes,
    fetch_global_forms,
    seed_form_definition,
)
from .public_intake_fixtures import assert_risk_annotation


V1_SEED_ID = UUID(hashlib.sha256(b"init-122:public-intake-global:v1").hexdigest()[:32])
V2_SEED_ID = UUID(hashlib.sha256(b"init-135:public-intake-global:v2").hexdigest()[:32])


def _seed_manifest(repo_root: Path) -> Path:
    return (
        repo_root
        / "gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml"
    )


def _seed_sql(repo_root: Path) -> str:
    manifests = yaml.safe_load_all(_seed_manifest(repo_root).read_text())
    sql = next(
        (
            manifest.get("data", {}).get("seed.sql")
            for manifest in manifests
            if isinstance(manifest, dict) and manifest.get("data", {}).get("seed.sql")
        ),
        None,
    )
    assert sql, "seed-public-intake-form.yaml must contain data.seed.sql block"
    sql = re.sub(r"^\s*BEGIN;\s*\n", "", sql, count=1)
    sql = re.sub(r"\n\s*COMMIT;\s*$", "\n", sql)
    return sql


def _run_seed_sql(database_url: str, repo_root: Path) -> str:
    with psycopg.connect(database_url) as connection:
        cursor = connection.execute(_seed_sql(repo_root))
        row = cursor.fetchone()
        assert row is not None
        connection.commit()
    return str(row[0])


def _insert_form_head(db: PostgresDatabase, *, current_seq: int) -> None:
    with db.connection() as connection:
        connection.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type,
                aggregate_id,
                current_seq,
                latest_change_id
            )
            VALUES ('application_form', 'application_form|global|', %s, NULL)
            """,
            (current_seq,),
        )


def _assert_tg4_annotation() -> None:
    assert_risk_annotation(
        group="TG-4",
        named_risk="public_intake_seed_v2_advances_only_v1_seed",
        level="particular-integration",
        source=".tmp/init-135/phase6/step6a-contract.md#TG-4-F3",
    )


def test_seed_v2_empty_db_inserts_v2_at_version_1(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-4;
    named_risk=public_intake_seed_v2_advances_only_v1_seed;
    level=integration; source=.tmp/init-135/phase6/step6a-contract.md#TG-4.
    """
    _assert_tg4_annotation()

    outcome = _run_seed_sql(governance_dsn, repo_root)

    assert outcome == "inserted seed v2"
    forms = fetch_global_forms(governance_db)
    assert [(form["id"], form["version"], form["status"]) for form in forms] == [
        (V2_SEED_ID, 1, "current")
    ]
    head = fetch_form_aggregate_head(governance_db)
    assert head is not None
    assert head["current_seq"] == 1
    assert head["latest_change_id"] is not None
    actions = fetch_form_actions(governance_db)
    changes = fetch_form_state_changes(governance_db)
    assert [action["action_type"] for action in actions] == ["form.publish"]
    assert actions[0]["request_json"]["version"] == 1
    assert [change["change_type"] for change in changes] == ["form.published"]
    assert changes[0]["aggregate_seq"] == 1
    assert changes[0]["payload_json"]["version"] == 1


def test_seed_v2_advances_v1_current_to_v2_at_version_2(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-4;
    named_risk=public_intake_seed_v2_advances_only_v1_seed;
    level=integration; source=.tmp/init-135/phase6/step6a-contract.md#TG-4.
    """
    _assert_tg4_annotation()
    seed_form_definition(governance_db, form_id=V1_SEED_ID, version=1)
    _insert_form_head(governance_db, current_seq=1)

    outcome = _run_seed_sql(governance_dsn, repo_root)

    assert outcome == "advanced v1 to v2"
    forms = fetch_global_forms(governance_db)
    assert [(form["id"], form["version"], form["status"]) for form in forms] == [
        (V1_SEED_ID, 1, "archived"),
        (V2_SEED_ID, 2, "current"),
    ]
    assert forms[0]["archived_at"] is not None
    head = fetch_form_aggregate_head(governance_db)
    assert head is not None
    assert head["current_seq"] == 2
    assert head["latest_change_id"] is not None
    actions = fetch_form_actions(governance_db)
    changes = fetch_form_state_changes(governance_db)
    assert [action["action_type"] for action in actions] == ["form.publish"]
    assert actions[0]["request_json"]["version"] == 2
    assert [change["change_type"] for change in changes] == ["form.published"]
    assert changes[0]["aggregate_seq"] == 2
    assert changes[0]["payload_json"]["version"] == 2


def test_seed_v2_no_op_when_officer_published_current(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-4;
    named_risk=public_intake_seed_v2_advances_only_v1_seed;
    level=integration; source=.tmp/init-135/phase6/step6a-contract.md#TG-4.
    """
    _assert_tg4_annotation()
    officer_form_id = uuid4()
    seed_form_definition(
        governance_db,
        form_id=officer_form_id,
        version=7,
        published_by_kind="user",
        published_by_id="officer",
    )
    _insert_form_head(governance_db, current_seq=7)

    outcome = _run_seed_sql(governance_dsn, repo_root)

    assert outcome == "officer-published form present; skipping seed"
    forms = fetch_global_forms(governance_db)
    assert [(form["id"], form["version"], form["status"]) for form in forms] == [
        (officer_form_id, 7, "current")
    ]
    head = fetch_form_aggregate_head(governance_db)
    assert head is not None
    assert head["current_seq"] == 7
    assert fetch_form_actions(governance_db) == []
    assert fetch_form_state_changes(governance_db) == []


def test_seed_v2_no_op_when_v2_already_current(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-4;
    named_risk=public_intake_seed_v2_advances_only_v1_seed;
    level=integration; source=.tmp/init-135/phase6/step6a-contract.md#TG-4.
    """
    _assert_tg4_annotation()
    seed_form_definition(governance_db, form_id=V2_SEED_ID, version=2)
    _insert_form_head(governance_db, current_seq=2)

    outcome = _run_seed_sql(governance_dsn, repo_root)

    assert outcome == "seed v2 already current; no-op"
    forms = fetch_global_forms(governance_db)
    assert [(form["id"], form["version"], form["status"]) for form in forms] == [
        (V2_SEED_ID, 2, "current")
    ]
    head = fetch_form_aggregate_head(governance_db)
    assert head is not None
    assert head["current_seq"] == 2
    assert fetch_form_actions(governance_db) == []
    assert fetch_form_state_changes(governance_db) == []


def test_seed_v2_preserves_bl002_fail_closed_guard(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-4;
    named_risk=public_intake_seed_v2_advances_only_v1_seed;
    level=integration; source=.tmp/init-135/phase6/step6a-contract.md#TG-4.
    """
    _assert_tg4_annotation()
    _insert_form_head(governance_db, current_seq=1)

    with pytest.raises(psycopg.Error, match="BL-002 fail-closed"):
        _run_seed_sql(governance_dsn, repo_root)

    assert fetch_global_forms(governance_db) == []
    head = fetch_form_aggregate_head(governance_db)
    assert head is not None
    assert head["current_seq"] == 1
    assert head["latest_change_id"] is None
