#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

pass() {
    echo "PASS: $*"
}

assert_file_exists() {
    local path="$1"
    [[ -f "$path" ]] || fail "Missing manifest: $path"
}

validate_yaml() {
    local path="$1"
    python3 -c "from pathlib import Path; import sys, yaml; yaml.safe_load(Path(sys.argv[1]).read_text())" "$path" \
        || fail "Invalid YAML: $path"
}

MANIFESTS=(
    "k8s/base/flux-system/kustomization.yaml"
    "k8s/base/monitoring/helmrelease.yaml"
    "k8s/base/secrets/helmrelease.yaml"
    "k8s/overlays/staging/kustomization.yaml"
)

for manifest in "${MANIFESTS[@]}"; do
    assert_file_exists "$manifest"
    validate_yaml "$manifest"
    pass "Valid YAML: $manifest"
done

python3 - <<'PY'
from pathlib import Path
import sys
import yaml

ROOT = Path.cwd()


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(relative_path: str):
    path = ROOT / relative_path
    try:
        return yaml.safe_load(path.read_text())
    except FileNotFoundError:
        fail(f"Missing manifest: {relative_path}")


def expect_equal(actual, expected, label: str) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def expect_present(value, label: str) -> None:
    if value is None or value == "":
        fail(f"{label}: value is required")


def expect_pinned_version(value, label: str) -> None:
    expect_present(value, label)
    if str(value).strip().lower() == "latest":
        fail(f"{label}: chart version must be pinned, not 'latest'")


def expect_resource_paths_exist(manifest_path: str, resources) -> None:
    manifest_dir = (ROOT / manifest_path).parent
    for resource in resources:
        candidate = (manifest_dir / resource).resolve()
        if not candidate.exists():
            fail(
                f"{manifest_path} references missing resource {resource!r} "
                f"(resolved to {candidate.relative_to(ROOT)!s})"
            )


def assert_flux_kustomization() -> None:
    path = "k8s/base/flux-system/kustomization.yaml"
    doc = load_yaml(path)
    expect_equal(doc.get("apiVersion"), "kustomize.config.k8s.io/v1beta1", f"{path} apiVersion")
    expect_equal(doc.get("kind"), "Kustomization", f"{path} kind")
    if "metadata" in doc:
        fail(f"{path} should not define metadata")

    resources = doc.get("resources")
    expect_equal(
        resources,
        [
            "gotk-components.yaml",
            "gotk-sync.yaml",
            "../secrets",
            "../monitoring",
        ],
        f"{path} resources",
    )
    expect_resource_paths_exist(path, resources)


def assert_monitoring_helmrelease() -> None:
    path = "k8s/base/monitoring/helmrelease.yaml"
    doc = load_yaml(path)
    expect_equal(doc.get("apiVersion"), "helm.toolkit.fluxcd.io/v2", f"{path} apiVersion")
    expect_equal(doc.get("kind"), "HelmRelease", f"{path} kind")

    metadata = doc.get("metadata") or {}
    expect_equal(metadata.get("name"), "kube-prometheus-stack", f"{path} metadata.name")
    expect_equal(metadata.get("namespace"), "monitoring", f"{path} metadata.namespace")

    spec = doc.get("spec") or {}
    expect_equal(spec.get("releaseName"), "kube-prometheus-stack", f"{path} spec.releaseName")
    expect_equal(spec.get("targetNamespace"), "monitoring", f"{path} spec.targetNamespace")
    expect_equal(spec.get("interval"), "30m", f"{path} spec.interval")
    expect_equal(spec.get("timeout"), "10m", f"{path} spec.timeout")

    install = spec.get("install") or {}
    expect_equal(install.get("createNamespace"), False, f"{path} spec.install.createNamespace")
    expect_equal(
        (install.get("remediation") or {}).get("retries"),
        3,
        f"{path} spec.install.remediation.retries",
    )

    upgrade = spec.get("upgrade") or {}
    expect_equal(
        (upgrade.get("remediation") or {}).get("retries"),
        3,
        f"{path} spec.upgrade.remediation.retries",
    )
    expect_equal(upgrade.get("cleanupOnFail"), True, f"{path} spec.upgrade.cleanupOnFail")

    chart_spec = ((spec.get("chart") or {}).get("spec") or {})
    expect_equal(chart_spec.get("chart"), "kube-prometheus-stack", f"{path} spec.chart.spec.chart")
    expect_pinned_version(chart_spec.get("version"), f"{path} spec.chart.spec.version")
    expect_equal(chart_spec.get("version"), "83.4.1", f"{path} spec.chart.spec.version")

    source_ref = chart_spec.get("sourceRef") or {}
    expect_equal(source_ref.get("kind"), "HelmRepository", f"{path} spec.chart.spec.sourceRef.kind")
    expect_equal(
        source_ref.get("name"),
        "prometheus-community",
        f"{path} spec.chart.spec.sourceRef.name",
    )
    expect_equal(
        source_ref.get("namespace"),
        "monitoring",
        f"{path} spec.chart.spec.sourceRef.namespace",
    )


def assert_secrets_helmrelease() -> None:
    path = "k8s/base/secrets/helmrelease.yaml"
    doc = load_yaml(path)
    expect_equal(doc.get("apiVersion"), "helm.toolkit.fluxcd.io/v2", f"{path} apiVersion")
    expect_equal(doc.get("kind"), "HelmRelease", f"{path} kind")

    metadata = doc.get("metadata") or {}
    expect_equal(metadata.get("name"), "sealed-secrets-controller", f"{path} metadata.name")
    expect_equal(metadata.get("namespace"), "sealed-secrets", f"{path} metadata.namespace")

    spec = doc.get("spec") or {}
    expect_equal(spec.get("releaseName"), "sealed-secrets", f"{path} spec.releaseName")
    expect_equal(spec.get("targetNamespace"), "sealed-secrets", f"{path} spec.targetNamespace")
    expect_equal(spec.get("interval"), "30m", f"{path} spec.interval")
    expect_equal(spec.get("timeout"), "5m", f"{path} spec.timeout")

    install = spec.get("install") or {}
    expect_equal(install.get("createNamespace"), False, f"{path} spec.install.createNamespace")
    expect_equal(
        (install.get("remediation") or {}).get("retries"),
        3,
        f"{path} spec.install.remediation.retries",
    )

    upgrade = spec.get("upgrade") or {}
    expect_equal(
        (upgrade.get("remediation") or {}).get("retries"),
        3,
        f"{path} spec.upgrade.remediation.retries",
    )
    expect_equal(upgrade.get("cleanupOnFail"), True, f"{path} spec.upgrade.cleanupOnFail")

    chart_spec = ((spec.get("chart") or {}).get("spec") or {})
    expect_equal(chart_spec.get("chart"), "sealed-secrets", f"{path} spec.chart.spec.chart")
    expect_pinned_version(chart_spec.get("version"), f"{path} spec.chart.spec.version")
    expect_equal(chart_spec.get("version"), "2.18.5", f"{path} spec.chart.spec.version")

    source_ref = chart_spec.get("sourceRef") or {}
    expect_equal(source_ref.get("kind"), "HelmRepository", f"{path} spec.chart.spec.sourceRef.kind")
    expect_equal(source_ref.get("name"), "sealed-secrets", f"{path} spec.chart.spec.sourceRef.name")
    expect_equal(
        source_ref.get("namespace"),
        "sealed-secrets",
        f"{path} spec.chart.spec.sourceRef.namespace",
    )


def assert_staging_overlay() -> None:
    path = "k8s/overlays/staging/kustomization.yaml"
    doc = load_yaml(path)
    expect_equal(doc.get("apiVersion"), "kustomize.config.k8s.io/v1beta1", f"{path} apiVersion")
    expect_equal(doc.get("kind"), "Kustomization", f"{path} kind")

    resources = doc.get("resources")
    expect_equal(
        resources,
        [
            "../../base/secrets",
            "../../base/monitoring",
        ],
        f"{path} resources",
    )
    expect_resource_paths_exist(path, resources)


assert_flux_kustomization()
print("PASS: flux-system kustomization contract")

assert_monitoring_helmrelease()
print("PASS: monitoring HelmRelease contract")

assert_secrets_helmrelease()
print("PASS: secrets HelmRelease contract")

assert_staging_overlay()
print("PASS: staging overlay contract")
PY

pass "All manifest validation checks passed."
