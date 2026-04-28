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


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_scheduled_backup_exists_as_restore_precondition() -> None:
    """INIT-112 / HOOKPOINT-B7: ScheduledBackup is only a restore precondition."""
    expected = _yaml(FIXTURE)["scheduled_backup"]
    scheduled_backup = _yaml(SCHEDULED_BACKUP)

    assert scheduled_backup["kind"] == "ScheduledBackup"
    assert scheduled_backup["metadata"]["name"] == expected["name"]
    assert scheduled_backup["metadata"]["namespace"] == expected["namespace"]
    assert scheduled_backup["spec"]["cluster"]["name"] == expected["cluster"]


def test_restore_drill_contract_fixture_defines_equality_oracle() -> None:
    """INIT-112 proposal: restore proof compares known inserted and restored data."""
    restore = _yaml(FIXTURE)["restore_drill"]

    assert RESTORE_SCRIPT.exists()
    assert restore["manual_backup_kind"] == "Backup"
    assert restore["inserted_row"] == restore["restored_row"]
    assert restore["schema"] == "sample_app"
    assert restore["table"] == "widgets"
