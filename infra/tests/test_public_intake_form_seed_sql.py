from __future__ import annotations

from uuid import UUID

from infra.tests.fixtures.public_intake_seed_contract import (
    SEED_ACTOR_ID,
    SEED_ACTOR_KIND,
    SEED_AGGREGATE_ID,
    SEED_FORM_NAME,
    SEED_REQUEST_SURFACE,
    SEED_SOURCE,
    SEED_TARGET_TYPE,
    assert_init122_risk_annotation,
    deterministic_public_intake_seed_form_id,
    fetch_public_intake_seed_rows,
    insert_officer_current_global_form,
)


pytest_plugins = ["infra.tests.fixtures.public_intake_seed"]


def test_seed_sql_inserts_aggregate_consistent_rows_and_is_idempotent(
    fresh_migrated_public_intake_db: str,
    public_intake_seed_runner,
) -> None:
    """Risk annotation: group=TG-1; named_risk=projection_only_or_duplicate_seed;
    level=component; source=proposals/04-public-intake-form-seed.md#test-intent-track.
    """
    assert_init122_risk_annotation(
        group="TG-1",
        named_risk="projection_only_or_duplicate_seed",
        level="component",
        source=SEED_SOURCE,
    )
    seed_id = deterministic_public_intake_seed_form_id()

    public_intake_seed_runner(fresh_migrated_public_intake_db)

    rows = fetch_public_intake_seed_rows(fresh_migrated_public_intake_db)
    assert len(rows["forms"]) == 1
    form = rows["forms"][0]
    assert form["id"] == seed_id
    assert form["scope_kind"] == "global"
    assert form["scope_id"] is None
    assert form["status"] == "current"
    assert form["version"] == 1
    assert form["target_type"] == SEED_TARGET_TYPE
    assert form["name"] == SEED_FORM_NAME
    assert {field["id"] for field in form["fields"]} == {
        "character_name",
        "application_text",
    }
    assert form["published_by_kind"] == SEED_ACTOR_KIND
    assert form["published_by_id"] == SEED_ACTOR_ID

    assert len(rows["actions"]) == 1
    action = rows["actions"][0]
    assert action["aggregate_id"] == SEED_AGGREGATE_ID
    assert action["action_type"] == "form.publish"
    assert action["actor_kind"] == SEED_ACTOR_KIND
    assert action["actor_id"] == SEED_ACTOR_ID
    assert action["status"] == "accepted"
    assert action["request_surface"] == SEED_REQUEST_SURFACE

    assert len(rows["state_changes"]) == 1
    state_change = rows["state_changes"][0]
    assert state_change["aggregate_id"] == SEED_AGGREGATE_ID
    assert state_change["aggregate_seq"] == 1
    assert state_change["change_type"] == "form.published"

    assert len(rows["heads"]) == 1
    head = rows["heads"][0]
    assert head["aggregate_id"] == SEED_AGGREGATE_ID
    assert head["current_seq"] == 1
    assert head["latest_change_id"] == state_change["id"]

    before_counts = {key: len(value) for key, value in rows.items()}
    public_intake_seed_runner(fresh_migrated_public_intake_db)
    rerun_rows = fetch_public_intake_seed_rows(fresh_migrated_public_intake_db)

    assert {key: len(value) for key, value in rerun_rows.items()} == before_counts
    assert rerun_rows["forms"][0]["version"] == 1
    assert rerun_rows["forms"][0]["id"] == seed_id


def test_seed_sql_skips_different_current_global_form_without_duplicate(
    fresh_migrated_public_intake_db: str,
    public_intake_seed_runner,
) -> None:
    """Risk annotation: group=TG-1; named_risk=operator_form_overwrite;
    level=component; source=proposals/04-public-intake-form-seed.md#assumption-register-A4.
    """
    assert_init122_risk_annotation(
        group="TG-1",
        named_risk="operator_form_overwrite",
        level="component",
        source="proposals/04-public-intake-form-seed.md#assumption-register-A4",
    )
    officer_form_id = insert_officer_current_global_form(fresh_migrated_public_intake_db)

    result = public_intake_seed_runner(fresh_migrated_public_intake_db)

    assert any(
        "officer-published form present; skipping seed" in notice
        for notice in result.notices
    )
    rows = fetch_public_intake_seed_rows(fresh_migrated_public_intake_db)
    assert len(rows["forms"]) == 1
    assert rows["forms"][0]["id"] == officer_form_id
    assert rows["forms"][0]["name"] == "Officer published global form"
    assert rows["forms"][0]["version"] == 1
    assert rows["forms"][0]["id"] != deterministic_public_intake_seed_form_id()
    assert rows["actions"] == []
    assert rows["state_changes"] == []
    assert rows["heads"] == []


def test_service_current_form_lookup_returns_seeded_global_form(
    api_import_path: None,
    fresh_migrated_public_intake_db: str,
    public_intake_seed_runner,
) -> None:
    """Risk annotation: group=TG-2; named_risk=current_form_api_404_after_seed;
    level=component; source=proposals/04-public-intake-form-seed.md#test-intent-track.
    """
    assert_init122_risk_annotation(
        group="TG-2",
        named_risk="current_form_api_404_after_seed",
        level="component",
        source=SEED_SOURCE,
    )
    from app.contracts.applications import ApplicationScope
    from app.repositories.db import PostgresDatabase
    from app.services.forms import get_current_form

    public_intake_seed_runner(fresh_migrated_public_intake_db)
    db = PostgresDatabase(dsn=fresh_migrated_public_intake_db)
    try:
        form, etag = get_current_form(
            db,
            scope=ApplicationScope(scope_kind="global", scope_id=None),
        )
    finally:
        db.close()

    assert UUID(str(form.id)) == deterministic_public_intake_seed_form_id()
    assert form.scope.scope_kind == "global"
    assert form.scope.scope_id is None
    assert form.name == SEED_FORM_NAME
    assert form.version == 1
    assert etag == '"1"'
    assert {field.id for field in form.fields} == {
        "character_name",
        "application_text",
    }
