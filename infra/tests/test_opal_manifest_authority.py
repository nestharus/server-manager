from __future__ import annotations

import json
from pathlib import Path

from infra.tests.fixtures.cedar_policy_source import (
    EXPECTED_OPAL_REPO_URL,
    LOCAL_ROOT,
    OPAL_RENDERED,
    OPAL_VALUES,
    bootstrap_job_name,
    bundle_config_map_name,
    deployment_env,
    files_containing,
    local_root_documents,
    yaml_document,
    yaml_documents,
)


def test_opal_server_manifest_uses_git_repo_cedar_policy_authority() -> None:
    """Risk annotation: group=TG-2; named_risk=empty_or_wrong_opal_policy_source;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#test-intent-track T2;
    assumptions=A1,A2.
    """
    values = yaml_document(OPAL_VALUES)
    docs = yaml_documents(OPAL_RENDERED)
    server_env = deployment_env(docs, "opal-server")

    assert values["server"]["policyRepoUrl"] == EXPECTED_OPAL_REPO_URL
    assert server_env["OPAL_POLICY_REPO_URL"] == EXPECTED_OPAL_REPO_URL
    # OPAL parses POLICY_REPO_POLICY_EXTENSIONS and FILTER_FILE_EXTENSIONS as
    # CSV (Confi.list with delimiter=","), not JSON. Single-extension values
    # therefore appear as plain strings, not as JSON arrays.
    assert values["server"]["extraEnv"]["OPAL_POLICY_REPO_POLICY_EXTENSIONS"] == ".cedar"
    assert server_env["OPAL_POLICY_REPO_POLICY_EXTENSIONS"] == ".cedar"
    assert values["server"]["extraEnv"]["OPAL_FILTER_FILE_EXTENSIONS"] == ".cedar"
    assert server_env["OPAL_FILTER_FILE_EXTENSIONS"] == ".cedar"
    assert int(values["server"]["extraEnv"]["OPAL_POLICY_REPO_POLLING_INTERVAL"]) == 30
    assert int(server_env["OPAL_POLICY_REPO_POLLING_INTERVAL"]) == 30


def test_opal_client_keeps_cedar_store_and_policy_updater_enabled() -> None:
    """Risk annotation: group=TG-2; named_risk=opal_client_policy_updater_disabled;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#contract C3;
    assumptions=A2.
    """
    docs = yaml_documents(OPAL_RENDERED)
    client_env = deployment_env(docs, "opal-client")

    assert client_env["OPAL_POLICY_STORE_TYPE"] == "CEDAR"
    assert client_env["OPAL_POLICY_STORE_URL"] == "http://localhost:8180"
    assert client_env["OPAL_POLICY_STORE_AUTH_TYPE"] == "none"
    assert client_env.get("OPAL_POLICY_UPDATER_ENABLED") != "False"


def test_local_root_renders_without_direct_cedar_writer_resources() -> None:
    """Risk annotation: group=TG-2; named_risk=direct_cedar_writer_survives;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#contract C4;
    assumptions=A5.
    """
    rendered = {
        (doc.get("kind"), doc.get("metadata", {}).get("name"))
        for doc in local_root_documents()
    }

    assert ("Job", bootstrap_job_name()) not in rendered
    assert ("ConfigMap", bundle_config_map_name()) not in rendered


def test_old_bootstrap_and_configmap_manifests_are_deleted() -> None:
    """Risk annotation: group=TG-2; named_risk=legacy_direct_writer_files_survive;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#contract C4;
    assumptions=A5.
    """
    opal_dir = LOCAL_ROOT / "auth" / "opal-cedar"

    assert not (opal_dir / "access-policy-configmap.yaml").exists()
    assert not (opal_dir / "bootstrap-job.yaml").exists()


def test_legacy_bootstrap_references_are_removed_from_runtime_surface() -> None:
    """Risk annotation: group=TG-2; named_risk=bootstrap_job_reference_survives;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#contract C6;
    assumptions=A5.
    """
    needle = bootstrap_job_name()
    matches = [
        path.relative_to(Path(__file__).resolve().parents[2]).as_posix()
        for root in (Path(__file__).resolve().parents[2] / "infra", Path(__file__).resolve().parents[2] / "gitops")
        for path in files_containing(root, needle)
    ]

    assert matches == []
