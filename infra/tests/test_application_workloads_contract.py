from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT
    / "infra"
    / "tests"
    / "fixtures"
    / "contracts"
    / "application_workloads_contract.yml"
)
APP_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "applications" / "server-manager"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _contract() -> dict:
    return _yaml(FIXTURE)


def test_api_discord_and_migration_use_fixture_supplied_images() -> None:
    """INIT-113 / SLICE-R.17: image tags are fixture inputs, not proof by literal."""
    expected = _contract()["images"]
    api = _yaml(APP_DIR / "api-deployment.yaml")
    discord = _yaml(APP_DIR / "discord-deployment.yaml")
    migration = _yaml(APP_DIR / "alembic-migration-job.yaml")

    api_image = api["spec"]["template"]["spec"]["containers"][0]["image"]
    discord_image = discord["spec"]["template"]["spec"]["containers"][0]["image"]
    migration_image = migration["spec"]["template"]["spec"]["containers"][0]["image"]

    assert api_image == expected["api"]
    assert discord_image == expected["discord"]
    assert migration_image == expected["api"]


def test_runtime_secret_scopes_are_infisical_managed() -> None:
    """INIT-113 handoff: runtime, database, and storage secrets come from Infisical."""
    expected = _contract()["runtime_secrets"]
    runtime = _yaml(APP_DIR / "runtime-infisicalsecret.yaml")
    database = _yaml(APP_DIR / "database-credentials-infisicalsecret.yaml")
    storage = _yaml(APP_DIR / "storage-credentials-infisicalsecret.yaml")

    scopes = {
        "server_manager": runtime["spec"]["authentication"]["universalAuth"][
            "secretsScope"
        ],
        "database": database["spec"]["authentication"]["universalAuth"][
            "secretsScope"
        ],
        "storage": storage["spec"]["authentication"]["universalAuth"]["secretsScope"],
    }

    for key, scope in scopes.items():
        assert scope["projectSlug"] == expected[key]["project"]
        assert scope["envSlug"] == expected[key]["environment"]
        assert scope["secretsPath"] == expected[key]["path"]


def test_database_migration_and_kong_ingress_contracts_are_present() -> None:
    """INIT-113 proposal: workload proof depends on migrated DB and Kong ingress."""
    expected = _contract()
    cluster = _yaml(APP_DIR / "postgres-cluster.yaml")
    ingress = _yaml(APP_DIR / "api-ingress.yaml")

    assert cluster["metadata"]["name"] == expected["database"]["cluster"]
    assert cluster["spec"]["bootstrap"]["initdb"]["database"] == expected["database"][
        "database"
    ]
    assert ingress["spec"]["ingressClassName"] == expected["ingress"]["class"]
    assert ingress["spec"]["rules"][0]["host"] == expected["ingress"]["host"]
