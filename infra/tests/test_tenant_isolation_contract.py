from __future__ import annotations

import json
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
