from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "backup_dr_contract.yml"
)
SCHEDULED_BACKUP = (
    REPO_ROOT
    / "gitops"
    / "channels"
    / "local"
    / "data-plane"
    / "sample-app"
    / "scheduled-backup.yaml"
)
RESTORE_SCRIPT = REPO_ROOT / "infra" / "scripts" / "run-cnpg-restore-drill.sh"
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_backup_dr_local.sh"
E2E_BACKUP_DR = REPO_ROOT / "infra" / "tests" / "e2e" / "tests" / "13-backup-dr.sh"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _contract() -> dict:
    return _yaml(FIXTURE)


def _fixture_path(relative: str) -> Path:
    return REPO_ROOT / relative


def test_scheduled_backup_exists_as_restore_precondition() -> None:
    """INIT-112 / HOOKPOINT-B7: ScheduledBackup is only a restore precondition."""
    expected = _contract()["scheduled_backup"]
    scheduled_backup = _yaml(SCHEDULED_BACKUP)

    assert scheduled_backup["kind"] == "ScheduledBackup"
    assert scheduled_backup["metadata"]["name"] == expected["name"]
    assert scheduled_backup["metadata"]["namespace"] == expected["namespace"]
    assert scheduled_backup["spec"]["cluster"]["name"] == expected["cluster"]


def test_restore_drill_contract_fixture_defines_equality_oracle() -> None:
    """INIT-112 proposal: restore proof compares known inserted and restored data."""
    restore = _contract()["restore_drill"]

    assert RESTORE_SCRIPT.exists()
    assert restore["manual_backup_kind"] == "Backup"
    assert restore["inserted_row"] == restore["restored_row"]
    assert restore["schema"] == "sample_app"
    assert restore["table"] == "widgets"


def test_backup_dr_fixtures_live_outside_test_bodies() -> None:
    """SLICE-R.16 fixtures are durable harness inputs, not inline test state."""
    contract = _contract()
    fixtures = contract["fixtures"]
    restore = contract["restore_drill"]

    seed_sql = _fixture_path(fixtures["seed_sql"]).read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS sample_app" in seed_sql
    assert "CREATE TABLE IF NOT EXISTS sample_app.widgets" in seed_sql
    assert restore["primary_key"] in seed_sql
    assert restore["inserted_row"]["source"] in seed_sql

    manual_backup = _yaml(_fixture_path(fixtures["manual_backup"]))
    assert manual_backup["apiVersion"] == "postgresql.cnpg.io/v1"
    assert manual_backup["kind"] == restore["manual_backup_kind"]
    assert manual_backup["metadata"]["name"] == restore["manual_backup_name"]
    assert manual_backup["metadata"]["namespace"] == contract["scheduled_backup"]["namespace"]
    assert manual_backup["spec"]["cluster"]["name"] == contract["scheduled_backup"]["cluster"]

    restore_cluster = _yaml(_fixture_path(fixtures["restore_cluster"]))
    assert restore_cluster["apiVersion"] == "postgresql.cnpg.io/v1"
    assert restore_cluster["kind"] == "Cluster"
    assert restore_cluster["metadata"]["name"] == restore["transient_cluster"]
    assert restore_cluster["metadata"]["name"] != contract["scheduled_backup"]["cluster"]
    assert (
        restore_cluster["spec"]["bootstrap"]["recovery"]["backup"]["name"]
        == restore["manual_backup_name"]
    )


def test_runtime_harness_requires_backup_and_restore_equality_proofs() -> None:
    """INIT-112 acceptance: runtime proof must expose backup object and data equality."""
    restore = _contract()["restore_drill"]
    validator = VALIDATOR.read_text(encoding="utf-8")
    e2e = E2E_BACKUP_DR.read_text(encoding="utf-8")

    assert "run-cnpg-restore-drill.sh" in validator
    for marker in restore["proof_markers"].values():
        assert marker in validator

    assert "--static-only" not in e2e
    assert "validate_backup_dr_local.sh" in e2e
