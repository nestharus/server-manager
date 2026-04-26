from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "gitops/channels/local/applications/server-manager"


def _yaml_doc(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_server_manager_application_subtree_is_included_from_local_root() -> None:
    local_root = (REPO_ROOT / "gitops/channels/local/kustomization.yaml").read_text(
        encoding="utf-8"
    )
    applications = (
        REPO_ROOT / "gitops/channels/local/applications/kustomization.yaml"
    ).read_text(encoding="utf-8")

    assert "applications" in local_root
    assert "server-manager" in applications


def test_server_manager_workloads_use_channel_registry_images() -> None:
    api = _yaml_doc(APP_DIR / "api-deployment.yaml")
    discord = _yaml_doc(APP_DIR / "discord-deployment.yaml")
    migration = _yaml_doc(APP_DIR / "alembic-migration-job.yaml")

    api_image = api["spec"]["template"]["spec"]["containers"][0]["image"]
    discord_image = discord["spec"]["template"]["spec"]["containers"][0]["image"]
    migration_image = migration["spec"]["template"]["spec"]["containers"][0]["image"]

    assert api_image == "k3d-humility-local:5000/local/server-manager-api:init-113-local"
    assert discord_image == "k3d-humility-local:5000/local/server-manager-discord:init-113-local"
    assert migration_image == api_image


def test_server_manager_database_backup_and_ingress_contracts() -> None:
    cluster = _yaml_doc(APP_DIR / "postgres-cluster.yaml")
    backup = _yaml_doc(APP_DIR / "scheduled-backup.yaml")
    ingress = _yaml_doc(APP_DIR / "api-ingress.yaml")

    assert cluster["metadata"]["name"] == "server-manager-postgres"
    assert cluster["spec"]["bootstrap"]["initdb"]["database"] == "server_manager"
    assert (
        cluster["spec"]["backup"]["barmanObjectStore"]["destinationPath"]
        == "s3://humility-local-backups/cnpg/local/server-manager-postgres"
    )
    assert backup["spec"]["cluster"]["name"] == "server-manager-postgres"
    assert ingress["spec"]["ingressClassName"] == "kong"
    assert ingress["spec"]["rules"][0]["host"] == "api.local.humility.local"
    assert ingress["spec"]["tls"][0]["secretName"] == "server-manager-api-local-ingress-tls"


def test_runtime_secrets_are_infisical_managed() -> None:
    runtime = _yaml_doc(APP_DIR / "runtime-infisicalsecret.yaml")
    database = _yaml_doc(APP_DIR / "database-credentials-infisicalsecret.yaml")
    storage = _yaml_doc(APP_DIR / "storage-credentials-infisicalsecret.yaml")

    assert runtime["kind"] == "InfisicalSecret"
    assert runtime["spec"]["authentication"]["universalAuth"]["secretsScope"] == {
        "projectSlug": "server-manager",
        "envSlug": "local",
        "secretsPath": "/runtime/local",
        "recursive": False,
    }
    assert (
        database["spec"]["authentication"]["universalAuth"]["secretsScope"]["secretsPath"]
        == "/postgres/local/server-manager"
    )
    assert (
        storage["spec"]["authentication"]["universalAuth"]["secretsScope"]["secretsPath"]
        == "/object-storage/local"
    )


def test_application_kustomization_renders() -> None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(APP_DIR)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "name: server-manager-api" in result.stdout
    assert "kind: AtlasMigration" in result.stdout
    assert "kind: ScheduledBackup" in result.stdout

