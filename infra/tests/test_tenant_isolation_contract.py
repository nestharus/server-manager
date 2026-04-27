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
SPAWN_PATH = REPO_ROOT / "infra" / "scripts" / "spawn_platform_channel.py"
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


def load_resolver():
    if "resolve_platform_channel" in sys.modules:
        return sys.modules["resolve_platform_channel"]

    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"resolver module is not loadable at {RESOLVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _yaml_docs(path: Path) -> list[dict]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def _tenant_docs() -> list[dict]:
    docs: list[dict] = []
    for path in sorted(TENANTS_DIR.glob("*/*.yaml")):
        if path.name == "kustomization.yaml":
            continue
        docs.extend(_yaml_docs(path))
    return docs


@pytest.fixture
def tmp_tenant_spawn_dir():
    out_dir = REPO_ROOT / ".tmp" / "pytest-tenant-spawn"
    shutil.rmtree(out_dir, ignore_errors=True)
    yield out_dir
    shutil.rmtree(out_dir, ignore_errors=True)


def test_tenant_isolation_channel_contract() -> None:
    resolver = load_resolver()
    channel = resolver.resolve_channel("local")
    isolation = channel["tenant_isolation"]

    # Intentionally strict: tenant_isolation additions are contract changes.
    assert isolation == {
        "namespace_pattern": "{tenant}-{channel}",
        "labels": {
            "tenant": "platform.humility.gg/tenant",
            "channel": "platform.humility.gg/channel",
            "tenant_channel": "platform.humility.gg/tenant-channel",
        },
        "rbac": {
            "operator_group_prefix": "humility:tenant",
            "role_name": "tenant-operator",
            "role_binding_name": "tenant-operators",
        },
        "network_policy": {
            "default_deny": True,
            "allow_dns_egress": True,
            "allow_same_tenant_cross_channel": True,
        },
        "cedar": {
            "principal_type": "Tenant",
            "resource_type": "TenantChannel",
            "action": 'Action::"tenant:channel:access"',
        },
        "infisical": {
            "project_pattern": "tenant-{tenant}-{channel}",
            "environment": "local",
            "secrets_path": "/runtime",
        },
        "samples": [
            {
                "tenant": "sample",
                "channels": ["local", "dev"],
                "operator_group": "humility:tenant:sample:operators",
            },
            {
                "tenant": "other",
                "channels": ["local"],
                "operator_group": "humility:tenant:other:operators",
            },
        ],
    }


def test_committed_tenant_manifests_enforce_namespace_rbac_netpol_and_infisical() -> None:
    docs = _tenant_docs()
    by_kind_name = {
        (doc["kind"], doc["metadata"]["name"], doc["metadata"].get("namespace")): doc
        for doc in docs
    }

    expected = {
        "sample-local": ("sample", "local", "tenant-sample-local"),
        "sample-dev": ("sample", "dev", "tenant-sample-dev"),
        "other-local": ("other", "local", "tenant-other-local"),
    }
    for namespace, (tenant, channel, project) in expected.items():
        ns = by_kind_name[("Namespace", namespace, None)]
        labels = ns["metadata"]["labels"]
        assert labels["platform.humility.gg/tenant"] == tenant
        assert labels["platform.humility.gg/channel"] == channel
        assert labels["platform.humility.gg/tenant-channel"] == namespace
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

        role = by_kind_name[("Role", "tenant-operator", namespace)]
        assert role["rules"][0]["verbs"] == [
            "get",
            "list",
            "watch",
            "create",
            "update",
            "patch",
            "delete",
        ]

        binding = by_kind_name[("RoleBinding", "tenant-operators", namespace)]
        assert binding["subjects"] == [
            {
                "kind": "Group",
                "name": f"humility:tenant:{tenant}:operators",
                "apiGroup": "rbac.authorization.k8s.io",
            }
        ]

        deny = by_kind_name[("NetworkPolicy", "default-deny", namespace)]
        assert deny["spec"] == {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}
        same_tenant = by_kind_name[
            ("NetworkPolicy", "allow-same-tenant-cross-channel", namespace)
        ]
        assert same_tenant["spec"]["ingress"][0]["from"][0]["namespaceSelector"][
            "matchLabels"
        ] == {"platform.humility.gg/tenant": tenant}
        assert same_tenant["spec"]["egress"][0]["to"][0]["namespaceSelector"][
            "matchLabels"
        ] == {"platform.humility.gg/tenant": tenant}

        secret = by_kind_name[("InfisicalSecret", "tenant-runtime", namespace)]
        scope = secret["spec"]["authentication"]["universalAuth"]["secretsScope"]
        assert scope["projectSlug"] == project
        assert scope["envSlug"] == "local"
        assert scope["secretsPath"] == "/runtime"


def test_cedar_bundle_contains_tenant_principals_and_resource_selectors() -> None:
    policies = json.loads((POLICY_DIR / "policies.json").read_text(encoding="utf-8"))
    by_id = {policy["id"]: policy["content"] for policy in policies}

    assert by_id["local-tenant-sample-local-access"] == (
        'permit(principal == Tenant::"sample", '
        'action == Action::"tenant:channel:access", '
        'resource == TenantChannel::"sample:local");'
    )
    assert by_id["local-tenant-sample-dev-access"] == (
        'permit(principal == Tenant::"sample", '
        'action == Action::"tenant:channel:access", '
        'resource == TenantChannel::"sample:dev");'
    )
    assert by_id["local-tenant-other-local-access"] == (
        'permit(principal == Tenant::"other", '
        'action == Action::"tenant:channel:access", '
        'resource == TenantChannel::"other:local");'
    )
    assert not any(
        'principal == Tenant::"sample"' in content
        and 'resource == TenantChannel::"other:local"' in content
        for content in by_id.values()
    )


def test_spawn_platform_channel_writes_tenant_scoped_resources(tmp_tenant_spawn_dir) -> None:
    out_dir = tmp_tenant_spawn_dir
    result = subprocess.run(
        [
            sys.executable,
            str(SPAWN_PATH),
            "--parent",
            "local",
            "--suffix",
            "pr-123",
            "--tenant",
            "sample",
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    channel = yaml.safe_load((out_dir / "channel.yaml").read_text(encoding="utf-8"))
    assert channel["id"] == "local-pr-123"
    assert channel["tenant"] == "sample"

    namespace_dir = out_dir / "tenant-resources" / "sample-local-pr-123"
    namespace = yaml.safe_load((namespace_dir / "namespace.yaml").read_text(encoding="utf-8"))
    assert namespace["metadata"]["name"] == "sample-local-pr-123"
    assert namespace["metadata"]["labels"]["platform.humility.gg/tenant"] == "sample"
    assert namespace["metadata"]["labels"]["platform.humility.gg/channel"] == "local-pr-123"

    rbac_docs = _yaml_docs(namespace_dir / "rbac.yaml")
    role_binding = next(doc for doc in rbac_docs if doc["kind"] == "RoleBinding")
    assert role_binding["subjects"][0]["name"] == "humility:tenant:sample:operators"

    policies = _yaml_docs(namespace_dir / "networkpolicies.yaml")
    same_tenant = next(
        doc for doc in policies if doc["metadata"]["name"] == "allow-same-tenant-cross-channel"
    )
    assert same_tenant["spec"]["egress"][0]["to"][0]["namespaceSelector"][
        "matchLabels"
    ] == {"platform.humility.gg/tenant": "sample"}

    secret = yaml.safe_load((namespace_dir / "infisicalsecret.yaml").read_text(encoding="utf-8"))
    scope = secret["spec"]["authentication"]["universalAuth"]["secretsScope"]
    assert scope["projectSlug"] == "tenant-sample-local-pr-123"
    assert scope["secretsPath"] == "/runtime"

    second = subprocess.run(
        [
            sys.executable,
            str(SPAWN_PATH),
            "--parent",
            "local",
            "--suffix",
            "pr-456",
            "--tenant",
            "sample",
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    generated_kustomization = yaml.safe_load(
        (out_dir / "tenant-resources" / "kustomization.yaml").read_text(encoding="utf-8")
    )
    assert generated_kustomization["resources"] == [
        "sample-local-pr-123",
        "sample-local-pr-456",
    ]


def test_local_root_renders_tenant_resources() -> None:
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
    assert "name: sample-local" in result.stdout
    assert "name: other-local" in result.stdout
    assert "projectSlug: tenant-sample-local" in result.stdout
