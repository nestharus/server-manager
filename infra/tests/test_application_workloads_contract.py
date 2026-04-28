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


def _pod_spec(workload: dict) -> dict:
    return workload["spec"]["template"]["spec"]


def _all_containers(workload: dict) -> list[dict]:
    pod_spec = _pod_spec(workload)
    return [*pod_spec.get("initContainers", []), *pod_spec.get("containers", [])]


def _secret_refs(workload: dict) -> set[str]:
    refs: set[str] = set()
    for container in _all_containers(workload):
        for env_from in container.get("envFrom", []):
            secret_ref = env_from.get("secretRef")
            if secret_ref and secret_ref.get("name"):
                refs.add(secret_ref["name"])
        for env in container.get("env", []):
            secret_key_ref = env.get("valueFrom", {}).get("secretKeyRef")
            if secret_key_ref and secret_key_ref.get("name"):
                refs.add(secret_key_ref["name"])
    return refs


def _container_images(workload: dict) -> list[str]:
    return [container["image"] for container in _all_containers(workload)]


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


def test_application_workload_fixture_state_is_externalized() -> None:
    """INIT-113 / SLICE-R.17: runtime proof data lives in fixtures."""
    expected = _contract()
    seed_path = REPO_ROOT / expected["fixtures"]["db_seed"]

    assert seed_path.is_file()
    seed_sql = seed_path.read_text(encoding="utf-8")
    assert "init113_workload_probe" in seed_sql
    assert expected["ingress"]["health_path"] == "/api/v1/health"
    assert set(expected["runtime"]) == {
        "namespace",
        "api_deployment",
        "discord_deployment",
        "migration_job",
    }


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


def test_api_and_discord_pods_start_from_infisical_managed_secrets() -> None:
    """INIT-113 contract: API and Discord pods consume Infisical-created secrets."""
    expected = _contract()["runtime_secrets"]
    runtime_secret = expected["server_manager"]["kubernetes_secret"]
    database_secret = expected["database"]["kubernetes_secret"]
    api = _yaml(APP_DIR / "api-deployment.yaml")
    discord = _yaml(APP_DIR / "discord-deployment.yaml")

    assert api["metadata"]["name"] == _contract()["runtime"]["api_deployment"]
    assert discord["metadata"]["name"] == _contract()["runtime"]["discord_deployment"]
    assert {runtime_secret, database_secret} <= _secret_refs(api)
    assert runtime_secret in _secret_refs(discord)


def test_database_migration_bucket_and_kong_ingress_contracts_are_present() -> None:
    """INIT-113 proposal: workload proof depends on migrated DB and Kong ingress."""
    expected = _contract()
    cluster = _yaml(APP_DIR / "postgres-cluster.yaml")
    migration = _yaml(APP_DIR / "alembic-migration-job.yaml")
    bucket = _yaml(APP_DIR / "object-storage-bucket-job.yaml")
    ingress = _yaml(APP_DIR / "api-ingress.yaml")

    assert cluster["metadata"]["name"] == expected["database"]["cluster"]
    assert cluster["spec"]["bootstrap"]["initdb"]["database"] == expected["database"][
        "database"
    ]
    assert migration["metadata"]["name"] == expected["runtime"]["migration_job"]
    assert expected["images"]["api"] in _container_images(migration)
    assert bucket["kind"] == "Job"
    assert (
        expected["runtime_secrets"]["storage"]["kubernetes_secret"]
        in _secret_refs(bucket)
    )
    assert ingress["spec"]["ingressClassName"] == expected["ingress"]["class"]
    assert ingress["spec"]["rules"][0]["host"] == expected["ingress"]["host"]
    backends = {
        path["backend"]["service"]["name"]
        for rule in ingress["spec"]["rules"]
        for path in rule.get("http", {}).get("paths", [])
    }
    assert expected["ingress"]["service"] in backends
