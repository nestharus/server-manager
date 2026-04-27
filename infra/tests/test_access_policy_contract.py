from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "infra" / "scripts" / "resolve_platform_channel.py"
POLICY_ID_PREFIX = "local-server-manager-api"
BUILDKITE_SERVICE_ID = "buildkite-agent.local"
POLICY_DIR = (
    REPO_ROOT
    / "policy"
    / "cedar"
    / "channels"
    / "local"
    / "services"
    / "server-manager-api"
)
OPAL_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "auth" / "opal-cedar"


def load_resolver():
    if "resolve_platform_channel" in sys.modules:
        return sys.modules["resolve_platform_channel"]

    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(
            f"resolver module is not loadable at {RESOLVER_PATH}; "
            "ensure the file exists and is valid Python"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _yaml_doc(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_access_policy_channel_contract() -> None:
    resolver = load_resolver()
    channel = resolver.resolve_channel("local")
    access_policy = channel["access_policy"]

    assert access_policy["policy_repo_path"] == "policy/cedar/channels/local"
    assert access_policy["bundle_config_map_name"] == "cedar-access-policy-bundle"
    assert access_policy["bootstrap_job_name"] == "cedar-access-policy-bootstrap"
    assert access_policy["services"]["server_manager_api"] == {
        "service_name": "server-manager-api",
        "bundle_path": "policy/cedar/channels/local/services/server-manager-api",
        "sample_user": "sample@local.humility.local",
        "sample_service_principal": 'Service::"buildkite-agent.local"',
    }
    assert access_policy["service_identity"]["audience"] == "server-manager-api"
    assert (
        access_policy["service_identity"]["identities"]["buildkite_agent"]["subject"]
        == "system:serviceaccount:buildkite-agent:buildkite-agent"
    )
    assert access_policy["credential_rotation"]["cadence_days"] == {
        "infisical_universal_auth_tokens": 30,
        "sops_age_key": 180,
        "sops_recipients": 180,
    }
    assert access_policy["break_glass"]["script"] == (
        "infra/scripts/break-glass-sops-recovery.sh"
    )
    assert access_policy["object_storage_policy"] == {
        "versioning": "enabled",
        "encryption": "sse-s3",
        "lifecycle_days": 30,
        "script": "infra/scripts/apply-object-storage-policies.sh",
    }
    assert access_policy["operator_rbac"]["crossplane_admin_binding_removed"] is True


def test_cedar_policy_bundle_is_structured_per_channel_and_service() -> None:
    manifest = _yaml_doc(POLICY_DIR / "manifest.yaml")
    policies = json.loads((POLICY_DIR / "policies.json").read_text(encoding="utf-8"))
    identities = json.loads(
        (POLICY_DIR / "service-identities.json").read_text(encoding="utf-8")
    )

    assert manifest["channel"] == "local"
    assert manifest["service"] == "server-manager-api"
    assert {policy["id"] for policy in policies} == {
        f"{POLICY_ID_PREFIX}-user-read",
        f"{POLICY_ID_PREFIX}-buildkite-deploy",
        "local-cluster-api-crossplane-reconcile",
        "local-tenant-sample-local-access",
        "local-tenant-sample-dev-access",
        "local-tenant-other-local-access",
    }
    assert identities["identities"]["buildkite_agent"]["cedar_principal"] == (
        f'Service::"{BUILDKITE_SERVICE_ID}"'
    )


def test_opal_bootstrap_uses_access_policy_bundle() -> None:
    config_map = _yaml_doc(OPAL_DIR / "access-policy-configmap.yaml")
    bootstrap = _yaml_doc(OPAL_DIR / "bootstrap-job.yaml")
    repo_policies = json.loads((POLICY_DIR / "policies.json").read_text(encoding="utf-8"))
    config_map_policies = json.loads(config_map["data"]["policies.json"])

    assert config_map["metadata"]["name"] == "cedar-access-policy-bundle"
    assert config_map_policies == repo_policies
    assert bootstrap["metadata"]["name"] == "cedar-access-policy-bootstrap"
    volumes = bootstrap["spec"]["template"]["spec"]["volumes"]
    policy_volume = next(
        (
            volume
            for volume in volumes
            if volume.get("configMap", {}).get("name") == "cedar-access-policy-bundle"
        ),
        None,
    )
    assert policy_volume is not None


def test_service_identity_issuer_and_operator_rbac_render() -> None:
    if shutil.which("kubectl") is None:
        pytest.skip("kubectl is required for kustomize rendering")

    result = subprocess.run(
        [
            "kubectl",
            "kustomize",
            "--load-restrictor=LoadRestrictionsNone",
            str(REPO_ROOT / "gitops" / "channels" / "local"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "name: service-identity-issuer" in result.stdout
    assert "name: platform-operator-appcluster-claims" in result.stdout
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if isinstance(doc, dict)]
    assert not any(
        doc.get("kind") == "ClusterRoleBinding"
        and doc.get("metadata", {}).get("name") == "crossplane-admin"
        for doc in docs
    )
