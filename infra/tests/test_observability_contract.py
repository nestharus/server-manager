from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "infra" / "scripts" / "resolve_platform_channel.py"
OBS_DIR = REPO_ROOT / "gitops/channels/local/observability"


def load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _yaml_docs(path: Path) -> list[dict]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def test_local_observability_channel_contract() -> None:
    resolver = load_resolver()
    observability = resolver.resolve_channel("local")["observability"]

    assert observability["namespace"] == "observability-system"
    assert observability["prometheus"]["image"] == "prom/prometheus:v2.54.1"
    assert observability["grafana"]["image"] == "grafana/grafana:11.2.0"
    assert observability["alertmanager"]["image"] == "prom/alertmanager:v0.27.0"
    assert observability["loki"]["image"] == "grafana/loki:3.1.1"
    assert observability["otel_collector"]["image"] == (
        "otel/opentelemetry-collector-contrib:0.106.1"
    )
    assert observability["object_storage"] == {
        "provider": "minio",
        "endpoint": "http://minio.minio-system.svc.cluster.local:9000",
        "bucket": "humility-local-observability",
        "region": "us-east-1",
        "credentials_secret_name": "loki-object-storage",
        "credentials_secret_namespace": "observability-system",
        "infisical_project": "platform-storage",
        "infisical_environment": "local",
        "infisical_path": "/object-storage/local/",
    }
    assert observability["tenant_label"] == "platform.humility.gg/tenant"
    assert observability["service_monitors"] == [
        "flux",
        "crossplane",
        "cert-manager",
        "infisical",
        "minio",
        "cnpg",
        "kong",
        "pomerium",
        "authentik",
        "opal",
        "server-manager-api",
        "buildkite-agent",
    ]
    assert observability["dashboards"] == [
        "flux-gitops-health",
        "cnpg",
        "kong-request-rate",
        "cedar-policy-decisions",
    ]
    assert observability["alerts"] == [
        "PodCrashLooping",
        "ClusterDown",
        "CertificateExpiringSoon",
    ]


def test_observability_raw_manifests_are_included_and_avoid_helm_controller() -> None:
    root = (REPO_ROOT / "gitops/channels/local/kustomization.yaml").read_text(
        encoding="utf-8"
    )
    assert "observability" in root

    rendered = subprocess.run(
        ["kubectl", "kustomize", str(OBS_DIR)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "kind: HelmRelease" not in rendered.stdout
    assert "helm.toolkit.fluxcd.io" not in rendered.stdout
    assert "kind: Deployment" in rendered.stdout
    assert "kind: DaemonSet" in rendered.stdout
    assert "kind: ServiceMonitor" in rendered.stdout


def test_service_monitors_cover_required_platform_components() -> None:
    docs = _yaml_docs(OBS_DIR / "service-monitors/service-monitors.yaml")
    names = [doc["metadata"]["name"] for doc in docs if doc["kind"] == "ServiceMonitor"]
    assert names == [
        "flux",
        "crossplane",
        "cert-manager",
        "infisical",
        "minio",
        "cnpg",
        "kong",
        "pomerium",
        "authentik",
        "opal",
        "server-manager-api",
        "buildkite-agent",
    ]


def test_loki_uses_minio_object_storage_and_infisical_credentials() -> None:
    config = yaml.safe_load(
        (OBS_DIR / "loki/configmap.yaml").read_text(encoding="utf-8")
    )
    deployment = yaml.safe_load(
        (OBS_DIR / "loki/deployment.yaml").read_text(encoding="utf-8")
    )
    infisical = _yaml_docs(OBS_DIR / "secrets/observability-infisicalsecret.yaml")

    loki_config = config["data"]["loki.yml"]
    assert "object_store: s3" in loki_config
    assert "endpoint: minio.minio-system.svc.cluster.local:9000" in loki_config
    assert "bucketnames: humility-local-observability" in loki_config
    assert "${MINIO_ROOT_USER}" in loki_config
    assert "${MINIO_ROOT_PASSWORD}" in loki_config

    env_refs = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    secret_refs = {
        item["name"]: item["valueFrom"]["secretKeyRef"]
        for item in env_refs
        if "valueFrom" in item and "secretKeyRef" in item["valueFrom"]
    }
    assert secret_refs == {
        "MINIO_ROOT_USER": {
            "name": "loki-object-storage",
            "key": "MINIO_ROOT_USER",
        },
        "MINIO_ROOT_PASSWORD": {
            "name": "loki-object-storage",
            "key": "MINIO_ROOT_PASSWORD",
        },
    }
    assert {doc["metadata"]["name"] for doc in infisical} == {
        "observability-runtime",
        "grafana-admin",
    }


def test_dashboards_are_tenant_aware_and_have_expected_uids() -> None:
    config = yaml.safe_load(
        (OBS_DIR / "dashboards/grafana-dashboards.yaml").read_text(encoding="utf-8")
    )
    dashboards = {
        name.removesuffix(".json"): json.loads(payload)
        for name, payload in config["data"].items()
    }

    assert set(dashboards) == {
        "flux-gitops-health",
        "cnpg",
        "kong-request-rate",
        "cedar-policy-decisions",
    }
    for filename_uid, dashboard in dashboards.items():
        assert dashboard["uid"] == filename_uid, (
            f"Dashboard UID must match filename: {filename_uid}"
        )
        variables = dashboard["templating"]["list"]
        tenant_var = next(
            (variable for variable in variables if variable["name"] == "tenant"),
            None,
        )
        assert tenant_var is not None, (
            f"dashboard {filename_uid} is missing tenant variable"
        )
        assert "label_values(up, tenant)" in tenant_var["query"]


def test_prometheus_rules_include_required_sample_alerts() -> None:
    config = yaml.safe_load(
        (OBS_DIR / "prometheus/rules-configmap.yaml").read_text(encoding="utf-8")
    )
    rules = yaml.safe_load(config["data"]["alerts.yml"])
    alert_names = [
        rule["alert"]
        for group in rules["groups"]
        for rule in group["rules"]
    ]
    assert alert_names == [
        "PodCrashLooping",
        "ClusterDown",
        "CertificateExpiringSoon",
    ]
