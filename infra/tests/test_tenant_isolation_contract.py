from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT
    / "infra"
    / "tests"
    / "fixtures"
    / "contracts"
    / "tenant_isolation_matrix.yml"
)
TENANTS_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "tenants"
SPAWN = REPO_ROOT / "infra" / "scripts" / "spawn_platform_channel.py"
POLICY_DIR = (
    REPO_ROOT
    / "policy"
    / "cedar"
    / "channels"
    / "local"
    / "services"
    / "server-manager-api"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _yaml_docs(path: Path) -> list[dict]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def _tenant_docs() -> list[dict]:
    docs: list[dict] = []
    for path in sorted(TENANTS_DIR.glob("*/*.yaml")):
        if path.name != "kustomization.yaml":
            docs.extend(_yaml_docs(path))
    return docs


def _policies() -> list[dict]:
    return json.loads((POLICY_DIR / "policies.json").read_text(encoding="utf-8"))


def _permits(policies: list[dict], principal: str, action: str, resource: str) -> bool:
    needles = [f"principal == {principal}", f"action == {action}", f"resource == {resource}"]
    return any(all(needle in policy.get("content", "") for needle in needles) for policy in policies)


def test_tenant_isolation_matrix_covers_required_allow_and_deny_surfaces() -> None:
    """SLICE-R.20 contract matrix covers all tenant isolation boundaries."""
    fixture = _yaml(FIXTURE)

    tenants_by_namespace = {tenant["namespace"]: tenant for tenant in fixture["tenants"]}
    assert {"sample-local", "sample-dev", "other-local"} <= set(tenants_by_namespace)
    for tenant in fixture["tenants"]:
        assert tenant["operator_group"] == f"humility:tenant:{tenant['tenant']}:operators"
        assert tenant["s3_prefix"] == f"tenants/{tenant['tenant']}/{tenant['channel']}/"
        assert tenant["db_schema"] == f"tenant_{tenant['tenant']}_{tenant['channel']}"

    matrix = fixture["access_matrix"]
    required_surfaces = {"namespace", "rbac", "network_policy", "infisical", "s3", "db"}
    assert required_surfaces <= {case["surface"] for case in matrix}
    for surface in required_surfaces:
        assert any(case["surface"] == surface and case["expected"] == "deny" for case in matrix)

    assert any(
        case["surface"] == "namespace"
        and case["actor_tenant"] == "sample"
        and case["target_namespace"] == "sample-dev"
        and case["expected"] == "allow"
        for case in matrix
    )
    assert any(
        case["surface"] == "network_policy"
        and case["source_namespace"] == "sample-local"
        and case["target_namespace"] == "sample-dev"
        and case["expected"] == "allow"
        for case in matrix
    )


def test_cedar_tenant_matrix_allows_same_tenant_and_denies_cross_tenant() -> None:
    """INIT-116 / SLICE-R.20: Cedar tenant behavior is allow plus denial."""
    fixture = _yaml(FIXTURE)
    policies = _policies()

    for case in fixture["cedar_decisions"]:
        permitted = _permits(
            policies,
            principal=case["principal"],
            action=case["action"],
            resource=case["resource"],
        )
        assert permitted is (case["effect"] == "allow"), case


def test_tenant_manifests_support_the_denial_boundary() -> None:
    """INIT-116 handoff: labels and NetworkPolicies support the cross-tenant denial."""
    fixture = _yaml(FIXTURE)
    docs = _tenant_docs()
    by_kind_name = {
        (doc["kind"], doc["metadata"]["name"], doc["metadata"].get("namespace")): doc
        for doc in docs
    }

    for tenant in fixture["tenants"]:
        namespace = tenant["namespace"]
        ns = by_kind_name[("Namespace", namespace, None)]
        labels = ns["metadata"]["labels"]
        assert labels["platform.humility.gg/tenant"] == tenant["tenant"]
        assert labels["platform.humility.gg/channel"] == tenant["channel"]
        assert labels["platform.humility.gg/tenant-channel"] == namespace
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

        binding = by_kind_name[("RoleBinding", "tenant-operators", namespace)]
        assert binding["subjects"][0]["name"] == tenant["operator_group"]

        default_deny = by_kind_name[("NetworkPolicy", "default-deny", namespace)]
        assert default_deny["spec"] == {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}

        same_tenant = by_kind_name[
            ("NetworkPolicy", "allow-same-tenant-cross-channel", namespace)
        ]
        assert same_tenant["spec"]["ingress"][0]["from"][0]["namespaceSelector"][
            "matchLabels"
        ] == {"platform.humility.gg/tenant": tenant["tenant"]}

        secret = by_kind_name[("InfisicalSecret", "tenant-runtime", namespace)]
        scope = secret["spec"]["authentication"]["universalAuth"]["secretsScope"]
        assert scope["projectSlug"] == tenant["infisical_project"]
        assert scope["secretsPath"] == "/runtime"


def test_spawn_tenant_resource_fixture_matches_contract(tmp_path: Path) -> None:
    """Tenant resource generation remains the fixture source for Step 6c."""
    fixture = _yaml(FIXTURE)
    sample_local = next(
        tenant for tenant in fixture["tenants"] if tenant["namespace"] == "sample-local"
    )
    out_dir = REPO_ROOT / ".tmp" / "tenant-isolation-contract" / tmp_path.name
    shutil.rmtree(out_dir, ignore_errors=True)

    try:
        subprocess.run(
            [
                sys.executable,
                str(SPAWN),
                "--parent",
                "local",
                "--suffix",
                "r20",
                "--tenant",
                sample_local["tenant"],
                "--out",
                str(out_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
        )

        generated_namespace = f"{sample_local['tenant']}-local-r20"
        resource_dir = out_dir / "tenant-resources" / generated_namespace
        assert (out_dir / "channel.yaml").is_file()
        assert resource_dir.is_dir()

        namespace_doc = _yaml(resource_dir / "namespace.yaml")
        assert namespace_doc["metadata"]["name"] == generated_namespace
        assert (
            namespace_doc["metadata"]["labels"]["platform.humility.gg/tenant"]
            == sample_local["tenant"]
        )
        assert (
            namespace_doc["metadata"]["labels"]["platform.humility.gg/channel"]
            == "local-r20"
        )

        secret_doc = _yaml(resource_dir / "infisicalsecret.yaml")
        scope = secret_doc["spec"]["authentication"]["universalAuth"]["secretsScope"]
        assert scope["projectSlug"] == "tenant-sample-local-r20"
        assert scope["secretsPath"] == "/runtime"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
