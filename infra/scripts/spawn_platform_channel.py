#!/usr/bin/env python3
"""Spawn an ephemeral child channel definition under .tmp."""

from __future__ import annotations

import argparse
import fcntl
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from resolve_platform_channel import ChannelError, REPO_ROOT, resolve_channel, write_error


CHANNEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TMP_ROOT = REPO_ROOT / ".tmp"
INFRA_CHANNELS = REPO_ROOT / "infra" / "channels"
INFRA_ROOTS = REPO_ROOT / "infra" / "roots"
TENANT_LABEL = "platform.humility.gg/tenant"
CHANNEL_LABEL = "platform.humility.gg/channel"
TENANT_CHANNEL_LABEL = "platform.humility.gg/tenant-channel"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validated_output_dir(raw_out: str, child_id: str) -> Path:
    out_path = Path(raw_out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    resolved = out_path.resolve(strict=False)
    tmp_root = TMP_ROOT.resolve(strict=False)
    channels_root = INFRA_CHANNELS.resolve(strict=False)
    roots_root = INFRA_ROOTS.resolve(strict=False)

    if not _is_relative_to(resolved, tmp_root):
        raise ChannelError(
            "schema_invalid",
            child_id,
            "spawn output path must be under .tmp/",
        )

    if _is_relative_to(resolved, channels_root) or _is_relative_to(resolved, roots_root):
        raise ChannelError(
            "schema_invalid",
            child_id,
            "spawn output path must not be under infra/channels/ or infra/roots/",
        )

    return resolved


def _tenant_namespace(tenant: str, channel: str) -> str:
    namespace = f"{tenant}-{channel}"
    if len(namespace) > 63:
        raise ChannelError(
            "schema_invalid",
            channel,
            f"tenant namespace {namespace!r} exceeds Kubernetes' 63-character limit",
        )
    return namespace


def _child_yaml(parent: dict[str, Any], suffix: str, tenant: str) -> dict[str, Any]:
    parent_id = str(parent["id"])
    child_id = f"{parent_id}-{suffix}"
    if not CHANNEL_ID_RE.fullmatch(suffix):
        raise ChannelError("schema_invalid", child_id, f"invalid suffix {suffix!r}")
    if not CHANNEL_ID_RE.fullmatch(tenant):
        raise ChannelError("schema_invalid", child_id, f"invalid tenant {tenant!r}")
    if not CHANNEL_ID_RE.fullmatch(child_id):
        raise ChannelError("schema_invalid", child_id, f"invalid child id {child_id!r}")
    _tenant_namespace(tenant, child_id)

    return {
        "schema_version": 1,
        "id": child_id,
        "parent": parent_id,
        "exposure": parent["exposure"],
        "tenant": tenant,
        "allow_ephemeral_children": False,
        "enabled_platforms": parent["enabled_platforms"],
    }


def _metadata_labels(tenant: str, channel: str) -> dict[str, str]:
    namespace = _tenant_namespace(tenant, channel)
    return {
        TENANT_LABEL: tenant,
        CHANNEL_LABEL: channel,
        TENANT_CHANNEL_LABEL: namespace,
        "pod-security.kubernetes.io/enforce": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
        "pod-security.kubernetes.io/audit": "restricted",
    }


def _tenant_resource_docs(parent: dict[str, Any], tenant: str, channel: str) -> list[dict[str, Any]]:
    isolation = parent.get("tenant_isolation", {})
    namespace = _tenant_namespace(tenant, channel)
    infisical = isolation.get("infisical", {})
    rbac = isolation.get("rbac", {})
    operator_group_prefix = rbac.get("operator_group_prefix", "humility:tenant")
    role_name = rbac.get("role_name", "tenant-operator")
    binding_name = rbac.get("role_binding_name", "tenant-operators")
    infisical_project = (
        infisical.get("project_pattern", "tenant-{tenant}-{channel}")
        .replace("{tenant}", tenant)
        .replace("{channel}", channel)
    )

    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": _metadata_labels(tenant, channel),
            },
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {
                "name": role_name,
                "namespace": namespace,
                "labels": {
                    TENANT_LABEL: tenant,
                    CHANNEL_LABEL: channel,
                    TENANT_CHANNEL_LABEL: namespace,
                },
            },
            "rules": [
                {
                    "apiGroups": ["", "apps", "batch", "networking.k8s.io"],
                    "resources": [
                        "configmaps",
                        "deployments",
                        "jobs",
                        "networkpolicies",
                        "pods",
                        "pods/log",
                        "secrets",
                        "services",
                    ],
                    "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"],
                }
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": binding_name,
                "namespace": namespace,
                "labels": {
                    TENANT_LABEL: tenant,
                    CHANNEL_LABEL: channel,
                    TENANT_CHANNEL_LABEL: namespace,
                },
            },
            "subjects": [
                {
                    "kind": "Group",
                    "name": f"{operator_group_prefix}:{tenant}:operators",
                    "apiGroup": "rbac.authorization.k8s.io",
                }
            ],
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": role_name,
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "default-deny", "namespace": namespace},
            "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "allow-dns-egress", "namespace": namespace},
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                                },
                                "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                            }
                        ],
                        "ports": [
                            {"protocol": "UDP", "port": 53},
                            {"protocol": "TCP", "port": 53},
                        ],
                    }
                ],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "allow-same-tenant-cross-channel", "namespace": namespace},
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {"from": [{"namespaceSelector": {"matchLabels": {TENANT_LABEL: tenant}}}]}
                ],
                "egress": [
                    {"to": [{"namespaceSelector": {"matchLabels": {TENANT_LABEL: tenant}}}]}
                ],
            },
        },
        {
            "apiVersion": "secrets.infisical.com/v1alpha1",
            "kind": "InfisicalSecret",
            "metadata": {
                "name": "tenant-runtime",
                "namespace": namespace,
                "labels": {
                    TENANT_LABEL: tenant,
                    CHANNEL_LABEL: channel,
                    TENANT_CHANNEL_LABEL: namespace,
                },
            },
            "spec": {
                "hostAPI": parent["infisical"]["server_url"],
                "authentication": {
                    "universalAuth": {
                        "credentialsRef": {
                            "secretName": parent["infisical"]["universal_auth_secret_name"],
                            "secretNamespace": parent["infisical"]["universal_auth_secret_namespace"],
                        },
                        "secretsScope": {
                            "projectSlug": infisical_project,
                            "envSlug": infisical.get("environment", parent["infisical"]["environment"]),
                            "secretsPath": infisical.get("secrets_path", "/runtime"),
                            "recursive": False,
                        },
                    }
                },
                "syncConfig": {"resyncInterval": parent["infisical"]["resync_interval"]},
                "managedSecretReference": {
                    "secretName": "tenant-runtime",
                    "secretNamespace": namespace,
                    "secretType": "Opaque",
                    "creationPolicy": "Owner",
                    "template": {"includeAllSecrets": True},
                },
            },
        },
    ]


def _write_tenant_resources(parent: dict[str, Any], tenant: str, channel: str, output_dir: Path) -> None:
    namespace = _tenant_namespace(tenant, channel)
    resources_dir = output_dir / "tenant-resources"
    namespace_dir = resources_dir / namespace
    resources_kustomization = resources_dir / "kustomization.yaml"
    namespace_dir.mkdir(parents=True, exist_ok=True)
    docs = _tenant_resource_docs(parent, tenant, channel)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        by_kind.setdefault(str(doc["kind"]), []).append(doc)
    file_groups = [
        ("namespace.yaml", by_kind.get("Namespace", [])),
        ("rbac.yaml", by_kind.get("Role", []) + by_kind.get("RoleBinding", [])),
        ("networkpolicies.yaml", by_kind.get("NetworkPolicy", [])),
        ("infisicalsecret.yaml", by_kind.get("InfisicalSecret", [])),
    ]
    filenames = [name for name, _ in file_groups]
    for filename, file_docs in file_groups:
        (namespace_dir / filename).write_text(
            yaml.safe_dump_all(file_docs, sort_keys=False),
            encoding="utf-8",
        )
    (namespace_dir / "kustomization.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "resources": filenames,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    lock_path = resources_dir / ".kustomization.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            resources = [namespace]
            if resources_kustomization.exists():
                existing = yaml.safe_load(resources_kustomization.read_text(encoding="utf-8"))
                if isinstance(existing, dict) and isinstance(existing.get("resources"), list):
                    resources = [str(item) for item in existing["resources"]]
                    if namespace not in resources:
                        resources.append(namespace)
            resources_kustomization.write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "kustomize.config.k8s.io/v1beta1",
                        "kind": "Kustomization",
                        "resources": resources,
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def spawn_channel(parent_id: str, suffix: str, out: str, tenant: str | None = None) -> Path:
    parent = resolve_channel(parent_id)
    child_id = f"{parent_id}-{suffix}"
    tenant_id = suffix if tenant is None else tenant

    if not parent.get("allow_ephemeral_children", False):
        raise ChannelError(
            "ephemeral_children_disabled",
            parent_id,
            f"channel {parent_id!r} does not allow ephemeral children",
        )

    output_dir = _validated_output_dir(out, child_id)
    payload = _child_yaml(parent, suffix, tenant_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "channel.yaml"
    output_file.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if "tenant_isolation" in parent and "infisical" in parent:
        _write_tenant_resources(parent, tenant_id, payload["id"], output_dir)
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, help="parent channel id")
    parser.add_argument("--suffix", required=True, help="ephemeral child suffix")
    parser.add_argument("--tenant", help="tenant id; defaults to suffix")
    parser.add_argument("--out", required=True, help="output directory; must be under .tmp/")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        spawn_channel(args.parent, args.suffix, args.out, args.tenant)
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
