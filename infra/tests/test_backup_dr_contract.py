from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "infra" / "scripts" / "resolve_platform_channel.py"


def load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"resolver module could not be loaded: {RESOLVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_backup_contract_targets_minio_bucket() -> None:
    resolver = load_resolver()

    channel = resolver.resolve_channel("local")

    assert channel["backup"] == {
        "provider": "minio",
        "endpoint": "http://minio.minio-system.svc.cluster.local:9000",
        "bucket": "humility-local-backups",
        "region": "us-east-1",
        "destination_path": "s3://humility-local-backups/cnpg/local/sample-app-postgres",
        "retention_policy": "7d",
        "schedule": "0 0 0 * * *",
        "credentials_secret_name": "backup-object-storage",
        "credentials_secret_namespace": "sample-app-db",
        "infisical_project": "platform-storage",
        "infisical_environment": "local",
        "infisical_path": "/object-storage/local/",
    }
    assert "backup" not in channel["data_plane"]


def test_dev_backup_contract_is_remote_only_vultr_object_storage() -> None:
    resolver = load_resolver()

    channel = resolver.resolve_channel("dev")

    assert channel["backup"]["provider"] == "vultr-object-storage"
    assert channel["backup"]["endpoint"] == "https://ewr1.vultrobjects.com"
    assert channel["backup"]["bucket"] == "humility-dev-backups"
    assert channel["backup"]["destination_path"] == "s3://humility-dev-backups/cnpg/dev/sample-app-postgres"
    assert channel["backup"]["infisical_path"] == "/object-storage/dev/"
    assert "backup" not in channel["data_plane"]


def test_local_backup_manifests_are_raw_gitops_resources() -> None:
    scheduled_backup = REPO_ROOT / "gitops" / "channels" / "local" / "data-plane" / "sample-app" / "scheduled-backup.yaml"
    bucket_job = REPO_ROOT / "gitops" / "channels" / "local" / "object-storage" / "buckets" / "backup-job.yaml"

    assert "kind: ScheduledBackup" in scheduled_backup.read_text(encoding="utf-8")
    assert "sample-app-postgres-daily" in scheduled_backup.read_text(encoding="utf-8")
    assert "kind: Job" in bucket_job.read_text(encoding="utf-8")
    assert "humility-local-backups" in bucket_job.read_text(encoding="utf-8")
