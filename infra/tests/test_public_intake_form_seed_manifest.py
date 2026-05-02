from __future__ import annotations

from pathlib import Path

import yaml

from infra.tests.fixtures.public_intake_seed_contract import (
    SEED_CONFIGMAP_NAME,
    SEED_JOB_NAME,
    SEED_MANIFEST_RELATIVE_PATH,
    SEED_SOURCE,
    assert_init122_risk_annotation,
)


pytest_plugins = ["infra.tests.fixtures.public_intake_seed"]


def _resource(documents: list[dict], *, kind: str, name: str) -> dict:
    match = next(
        (
            document
            for document in documents
            if document.get("kind") == kind
            and document.get("metadata", {}).get("name") == name
        ),
        None,
    )
    assert match is not None, f"missing {kind}/{name}"
    return match


def test_public_intake_seed_manifest_contains_configmap_and_hardened_job(
    public_intake_seed_manifest_path: Path,
    public_intake_seed_manifest_documents: list[dict],
) -> None:
    """Risk annotation: group=TG-3; named_risk=seed_manifest_omitted_or_unhardened;
    level=particular-integration; source=planning/proposals/04-public-intake-form-seed.md#test-intent-track.
    """
    assert_init122_risk_annotation(
        group="TG-3",
        named_risk="seed_manifest_omitted_or_unhardened",
        level="particular-integration",
        source=SEED_SOURCE,
    )
    assert public_intake_seed_manifest_path.is_file()
    assert len(public_intake_seed_manifest_documents) >= 2

    configmap = _resource(
        public_intake_seed_manifest_documents,
        kind="ConfigMap",
        name=SEED_CONFIGMAP_NAME,
    )
    seed_sql = configmap.get("data", {}).get("seed.sql")
    assert isinstance(seed_sql, str)
    assert seed_sql.strip()

    job = _resource(
        public_intake_seed_manifest_documents,
        kind="Job",
        name=SEED_JOB_NAME,
    )
    assert job["spec"]["backoffLimit"] == 6
    pod_spec = job["spec"]["template"]["spec"]
    assert pod_spec["restartPolicy"] == "OnFailure"
    assert pod_spec["automountServiceAccountToken"] is False

    pod_security = pod_spec["securityContext"]
    assert pod_security["runAsNonRoot"] is True
    assert pod_security["seccompProfile"]["type"] == "RuntimeDefault"

    container = pod_spec["containers"][0]
    container_security = container["securityContext"]
    assert container_security["runAsNonRoot"] is True
    assert container_security["allowPrivilegeEscalation"] is False
    assert "ALL" in container_security["capabilities"]["drop"]
    assert container_security["readOnlyRootFilesystem"] is True

    database_env = next(
        env for env in container["env"] if env.get("name") == "DATABASE_URL"
    )
    assert database_env["valueFrom"]["secretKeyRef"] == {
        "name": "server-manager-postgres-url",
        "key": "url",
    }

    volumes = {volume["name"]: volume for volume in pod_spec["volumes"]}
    seed_volumes = [
        volume
        for volume in volumes.values()
        if volume.get("configMap", {}).get("name") == SEED_CONFIGMAP_NAME
    ]
    assert len(seed_volumes) == 1
    assert seed_volumes[0]["configMap"]["items"] == [
        {"key": "seed.sql", "path": "seed.sql"}
    ]

    mounts = container["volumeMounts"]
    seed_mount = next(
        mount for mount in mounts if mount["name"] == seed_volumes[0]["name"]
    )
    assert seed_mount["mountPath"] == "/seed/seed.sql"
    assert seed_mount["subPath"] == "seed.sql"
    assert seed_mount["readOnly"] is True

    command_text = "\n".join(
        str(part)
        for part in [*container.get("command", []), *container.get("args", [])]
    )
    assert "pg_isready" in command_text
    assert "120" in command_text
    assert "psql" in command_text
    assert "ON_ERROR_STOP=1" in command_text
    assert "/seed/seed.sql" in command_text


def test_public_intake_seed_manifest_is_ordered_after_alembic_job(
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-3; named_risk=seed_runs_before_migrations;
    level=particular-integration; source=planning/proposals/04-public-intake-form-seed.md#test-intent-track.
    """
    assert_init122_risk_annotation(
        group="TG-3",
        named_risk="seed_runs_before_migrations",
        level="particular-integration",
        source=SEED_SOURCE,
    )
    kustomization_path = (
        repo_root
        / "gitops/channels/local/applications/server-manager/kustomization.yaml"
    )
    kustomization = yaml.safe_load(kustomization_path.read_text(encoding="utf-8"))
    resources = kustomization["resources"]

    alembic_index = resources.index("alembic-migration-job.yaml")
    seed_index = resources.index(SEED_MANIFEST_RELATIVE_PATH.name)
    assert seed_index == alembic_index + 1
