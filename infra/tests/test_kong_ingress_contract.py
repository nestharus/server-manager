from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "infra" / "scripts" / "resolve_platform_channel.py"
_RESOLVER_MODULE = None


def load_resolver():
    global _RESOLVER_MODULE
    if _RESOLVER_MODULE is not None:
        return _RESOLVER_MODULE

    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    if spec is None:
        raise FileNotFoundError(f"resolver module not found at {RESOLVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"resolver module has no loader: {RESOLVER_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RESOLVER_MODULE = module
    return module


def test_local_ingress_contract_matches_kong_render() -> None:
    resolver = load_resolver()
    channel = resolver.resolve_channel("local")
    ingress = channel["ingress"]
    service = ingress["default_service"]

    values = yaml.safe_load(
        (REPO_ROOT / "gitops/channels/local/ingress/kong/render-values.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert ingress["provider"] == "kong"
    assert ingress["gateway_namespace"] == "kong-system"
    assert ingress["chart_name"] == "kong/kong"
    assert ingress["chart_version"] == "3.2.0"
    assert ingress["gateway_image"] == "kong:3.9"
    assert ingress["controller_image"] == "kong/kubernetes-ingress-controller:3.5"
    assert ingress["ingress_class_name"] == "kong"
    assert ingress["gateway_deployment_name"] == "kong-kong"
    assert ingress["proxy_service_name"] == "kong-kong-proxy"
    assert ingress["proxy_service_type"] == "ClusterIP"
    assert ingress["local_dns_namespace"] == "local"
    assert ingress["local_cluster_issuer_name"] == channel["tls"]["local_cluster_issuer_name"]
    assert service == {
        "name": "minio",
        "namespace": "minio-system",
        "service_port": 9000,
        "local_host": "minio.local.humility.local",
        "remote_host": "minio.local.humility.gg",
        "tls_secret_name": "minio-local-ingress-tls",
        "proof_path": "/minio/health/ready",
    }
    assert values["image"] == {"repository": "kong", "tag": "3.9", "pullPolicy": "IfNotPresent"}
    assert values["ingressController"]["image"] == {
        "repository": "kong/kubernetes-ingress-controller",
        "tag": "3.5",
    }
    assert values["ingressController"]["ingressClass"] == "kong"
    assert values["proxy"]["type"] == "ClusterIP"


def test_dev_ingress_contract_uses_remote_channel_host() -> None:
    resolver = load_resolver()
    ingress = resolver.resolve_channel("dev")["ingress"]

    assert ingress["proxy_service_type"] == "LoadBalancer"
    assert ingress["remote_domain"] == "humility.gg"
    assert ingress["default_service"]["remote_host"] == "minio.dev.humility.gg"


def test_minio_ingress_manifest_matches_channel_contract() -> None:
    resolver = load_resolver()
    ingress = resolver.resolve_channel("local")["ingress"]
    service = ingress["default_service"]

    manifest = yaml.safe_load(
        (
            REPO_ROOT / "gitops/channels/local/ingress/default-services/minio/ingress.yaml"
        ).read_text(encoding="utf-8")
    )
    alias = yaml.safe_load(
        (
            REPO_ROOT / "gitops/channels/local/ingress/default-services/minio/alias-service.yaml"
        ).read_text(encoding="utf-8")
    )

    assert manifest["spec"]["ingressClassName"] == ingress["ingress_class_name"]
    assert manifest["spec"]["tls"] == [
        {"hosts": [service["local_host"]], "secretName": service["tls_secret_name"]}
    ]
    assert manifest["spec"]["rules"][0]["host"] == service["local_host"]
    assert manifest["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"] == {
        "name": service["name"],
        "port": {"number": service["service_port"]},
    }
    assert alias["metadata"]["namespace"] == ingress["local_dns_namespace"]
    assert alias["spec"]["externalName"] == (
        f"{ingress['proxy_service_name']}.{ingress['gateway_namespace']}.svc.cluster.local"
    )
