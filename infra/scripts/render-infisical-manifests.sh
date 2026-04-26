#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

HELM_REPO_NAME="infisical-helm-charts"
HELM_REPO_URL="https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/"
SERVER_CHART="infisical-standalone"
SERVER_CHART_VERSION="1.8.0"
SERVER_RELEASE="infisical"
SERVER_NAMESPACE="infisical-system"
SERVER_VALUES="${REPO_ROOT}/gitops/channels/local/infisical/server/render-values.yaml"
SERVER_RENDERED="${REPO_ROOT}/gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml"

OPERATOR_CHART="secrets-operator"
OPERATOR_CHART_VERSION="0.10.32"
OPERATOR_RELEASE="infisical-operator"
OPERATOR_NAMESPACE="infisical-system"
OPERATOR_VALUES="${REPO_ROOT}/gitops/channels/local/infisical/operator/render-values.yaml"
OPERATOR_RENDERED="${REPO_ROOT}/gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml"
OPERATOR_UPSTREAM_REPO="https://github.com/Infisical/kubernetes-operator.git"
OPERATOR_UPSTREAM_TAG="infisical-k8-operator/v0.10.32"

SERVER_EXPECTED_IMAGES=(
  "infisical/infisical:v0.151.0"
  "mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16"
  "mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18"
)

OPERATOR_EXPECTED_IMAGES=(
  "infisical/kubernetes-operator:v0.10.32"
)

OPERATOR_EXPECTED_CRDS=(
  "clustergenerators.secrets.infisical.com"
  "infisicaldynamicsecrets.secrets.infisical.com"
  "infisicalpushsecrets.secrets.infisical.com"
  "infisicalsecrets.secrets.infisical.com"
  "passwords.secrets.infisical.com"
  "uuids.secrets.infisical.com"
)

CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: render-infisical-manifests.sh [--check]

Renders the pinned Infisical standalone and Operator manifests.

Options:
  --check   Render to a temporary file and fail if committed manifests differ
  -h, --help
            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "missing required command: ${command_name}" >&2
    exit 1
  fi
}

python_bin() {
  if command -v python >/dev/null 2>&1; then
    command -v python
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    return 1
  fi
}

render_server() {
  local output_path="$1"
  local raw_path="${output_path}.raw"

  helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" --force-update >/dev/null
  helm repo update "$HELM_REPO_NAME" >/dev/null
  helm template "$SERVER_RELEASE" "${HELM_REPO_NAME}/${SERVER_CHART}" \
    --version "$SERVER_CHART_VERSION" \
    --namespace "$SERVER_NAMESPACE" \
    --values "$SERVER_VALUES" \
    > "$raw_path"

  "$PYTHON_BIN" - "$raw_path" "$output_path" <<'PY'
import sys
from pathlib import Path

import yaml

raw_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

HELM_LABELS = {
    "app.kubernetes.io/managed-by",
    "helm.sh/chart",
    "chart",
    "heritage",
}
HELM_ANNOTATION_PREFIXES = (
    "helm.sh/",
    "meta.helm.sh/",
)
HELM_ANNOTATIONS = {
    "updatedAt",
}


def strip_metadata(value):
    if isinstance(value, dict):
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            labels = metadata.get("labels")
            if isinstance(labels, dict):
                for key in list(labels):
                    if key in HELM_LABELS:
                        labels.pop(key, None)
                if not labels:
                    metadata.pop("labels", None)

            annotations = metadata.get("annotations")
            if isinstance(annotations, dict):
                for key in list(annotations):
                    if key in HELM_ANNOTATIONS or key.startswith(HELM_ANNOTATION_PREFIXES):
                        annotations.pop(key, None)
                if not annotations:
                    metadata.pop("annotations", None)

        for child in value.values():
            strip_metadata(child)
    elif isinstance(value, list):
        for child in value:
            strip_metadata(child)


NAMESPACED_KINDS = {
    "ConfigMap",
    "Deployment",
    "NetworkPolicy",
    "PersistentVolumeClaim",
    "Pod",
    "Role",
    "RoleBinding",
    "Secret",
    "Service",
    "ServiceAccount",
    "StatefulSet",
}
SERVER_NAMESPACE = "infisical-system"
BOOTSTRAP_SECRET = "infisical-server-bootstrap"


def add_namespace(value):
    if not isinstance(value, dict):
        return
    if value.get("kind") in NAMESPACED_KINDS:
        metadata = value.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.setdefault("namespace", SERVER_NAMESPACE)


def replace_secret_backed_env(value):
    if not isinstance(value, dict):
        return
    spec = value.get("spec")
    template = spec.get("template") if isinstance(spec, dict) else None
    pod_spec = template.get("spec") if isinstance(template, dict) else None
    containers = pod_spec.get("containers") if isinstance(pod_spec, dict) else None
    if not isinstance(containers, list):
        return
    for container in containers:
        if not isinstance(container, dict):
            continue
        env = container.get("env")
        if not isinstance(env, list):
            continue
        filtered = []
        seen_secret_backed = set()
        for item in env:
            if not isinstance(item, dict):
                filtered.append(item)
                continue
            name = item.get("name")
            if name == "DB_CONNECTION_URI":
                item = {
                    "name": name,
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": BOOTSTRAP_SECRET,
                            "key": "DB_CONNECTION_URI",
                        },
                    },
                }
            elif name == "REDIS_URL":
                item = {
                    "name": name,
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": BOOTSTRAP_SECRET,
                            "key": "REDIS_URL",
                        },
                    },
                }
            if name in {"DB_CONNECTION_URI", "REDIS_URL"}:
                if name in seen_secret_backed:
                    continue
                seen_secret_backed.add(name)
            filtered.append(item)
        container["env"] = filtered


documents = [doc for doc in yaml.safe_load_all(raw_path.read_text(encoding="utf-8")) if doc]
for document in documents:
    strip_metadata(document)
    add_namespace(document)
    replace_secret_backed_env(document)

with output_path.open("w", encoding="utf-8") as handle:
    yaml.safe_dump_all(
        documents,
        handle,
        explicit_start=True,
        sort_keys=False,
        default_flow_style=False,
    )
PY

  rm -f "$raw_path"
}

render_operator() {
  local output_path="$1"
  local raw_path="${output_path}.raw"
  local upstream_dir="${output_path}.upstream"

  helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" --force-update >/dev/null
  helm repo update "$HELM_REPO_NAME" >/dev/null
  helm template "$OPERATOR_RELEASE" "${HELM_REPO_NAME}/${OPERATOR_CHART}" \
    --version "$OPERATOR_CHART_VERSION" \
    --namespace "$OPERATOR_NAMESPACE" \
    --values "$OPERATOR_VALUES" \
    > "$raw_path"

  # The packaged v0.10.32 chart omits the Password and UUID CRD templates.
  # Pull the missing CRD bases from the matching upstream release tag.
  if ! git clone --depth 1 --quiet --branch "$OPERATOR_UPSTREAM_TAG" "$OPERATOR_UPSTREAM_REPO" "$upstream_dir" 2>&1; then
    echo "ERROR: failed to clone $OPERATOR_UPSTREAM_REPO at $OPERATOR_UPSTREAM_TAG" >&2
    return 1
  fi

  "$PYTHON_BIN" - "$raw_path" "$output_path" "$upstream_dir" "${OPERATOR_EXPECTED_CRDS[@]}" <<'PY'
import sys
from pathlib import Path

import yaml

raw_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
upstream_dir = Path(sys.argv[3])
expected_crds = sys.argv[4:]

HELM_LABELS = {
    "app.kubernetes.io/managed-by",
    "helm.sh/chart",
    "chart",
    "heritage",
}
HELM_ANNOTATION_PREFIXES = (
    "helm.sh/",
    "meta.helm.sh/",
)
HELM_ANNOTATIONS = {
    "updatedAt",
}


def strip_metadata(value):
    if isinstance(value, dict):
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            labels = metadata.get("labels")
            if isinstance(labels, dict):
                for key in list(labels):
                    if key in HELM_LABELS:
                        labels.pop(key, None)
                if not labels:
                    metadata.pop("labels", None)

            annotations = metadata.get("annotations")
            if isinstance(annotations, dict):
                for key in list(annotations):
                    if key in HELM_ANNOTATIONS or key.startswith(HELM_ANNOTATION_PREFIXES):
                        annotations.pop(key, None)
                if not annotations:
                    metadata.pop("annotations", None)

        for child in value.values():
            strip_metadata(child)
    elif isinstance(value, list):
        for child in value:
            strip_metadata(child)


def crd_name(document):
    if not isinstance(document, dict):
        return None
    if document.get("kind") != "CustomResourceDefinition":
        return None
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    name = metadata.get("name")
    return name if isinstance(name, str) else None


NAMESPACED_KINDS = {
    "ConfigMap",
    "Deployment",
    "NetworkPolicy",
    "PersistentVolumeClaim",
    "Pod",
    "Role",
    "RoleBinding",
    "Secret",
    "Service",
    "ServiceAccount",
    "StatefulSet",
}
OPERATOR_NAMESPACE = "infisical-system"


def add_namespace(value):
    if not isinstance(value, dict):
        return
    if value.get("kind") in NAMESPACED_KINDS:
        metadata = value.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.setdefault("namespace", OPERATOR_NAMESPACE)


documents = [doc for doc in yaml.safe_load_all(raw_path.read_text(encoding="utf-8")) if doc]
for document in documents:
    strip_metadata(document)
    add_namespace(document)

found_crds = {name for document in documents if (name := crd_name(document))}
for name in expected_crds:
    if name in found_crds:
        continue
    source_name = name
    suffix = ".secrets.infisical.com"
    if source_name.endswith(suffix):
        source_name = source_name[:-len(suffix)]
    source = upstream_dir / "config" / "crd" / "bases" / f"secrets.infisical.com_{source_name}.yaml"
    if not source.is_file():
        raise SystemExit(f"missing upstream CRD source for {name}: {source}")
    source_docs = [doc for doc in yaml.safe_load_all(source.read_text(encoding="utf-8")) if doc]
    matching_docs = [doc for doc in source_docs if crd_name(doc) == name]
    if len(matching_docs) != 1:
        raise SystemExit(f"expected one upstream CRD document for {name}, found {len(matching_docs)}")
    strip_metadata(matching_docs[0])
    add_namespace(matching_docs[0])
    documents.append(matching_docs[0])
    found_crds.add(name)

if found_crds != set(expected_crds):
    raise SystemExit(f"operator CRD set mismatch: found={sorted(found_crds)!r}")

with output_path.open("w", encoding="utf-8") as handle:
    yaml.safe_dump_all(
        documents,
        handle,
        explicit_start=True,
        sort_keys=False,
        default_flow_style=False,
    )
PY

  rm -rf "$raw_path" "$upstream_dir"
}

assert_no_helm_runtime_objects() {
  local path="$1"
  if grep -Eq '^[[:space:]]*kind:[[:space:]]*(HelmRelease|OCIRepository)[[:space:]]*$' "$path"; then
    echo "rendered manifests contain HelmRelease or OCIRepository: ${path}" >&2
    exit 1
  fi
}

assert_image_set() {
  local path="$1"
  shift
  "$PYTHON_BIN" - "$path" "${EXPECTED_IMAGES[@]}" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
expected = set(sys.argv[2:])
found = set()


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "image" and isinstance(child, str):
                found.add(child)
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)


for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
    walk(document)

if found != expected:
    missing = sorted(expected - found)
    unexpected = sorted(found - expected)
    if missing:
        print("missing expected images:", ", ".join(missing), file=sys.stderr)
    if unexpected:
        print("unexpected images:", ", ".join(unexpected), file=sys.stderr)
    sys.exit(1)

for image in sorted(found):
    print(image)
PY
}

assert_crd_set() {
  local path="$1"
  shift
  "$PYTHON_BIN" - "$path" "$@" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
expected = set(sys.argv[2:])
found = set()

for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
    if not isinstance(document, dict) or document.get("kind") != "CustomResourceDefinition":
        continue
    metadata = document.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("name"), str):
        found.add(metadata["name"])

if found != expected:
    missing = sorted(expected - found)
    unexpected = sorted(found - expected)
    if missing:
        print("missing expected CRDs:", ", ".join(missing), file=sys.stderr)
    if unexpected:
        print("unexpected CRDs:", ", ".join(unexpected), file=sys.stderr)
    sys.exit(1)

for crd in sorted(found):
    print(crd)
PY
}

require_command helm
require_command git
if ! PYTHON_BIN="$(python_bin)"; then
  echo "missing required command: python or python3" >&2
  exit 1
fi

if [[ ! -f "$SERVER_VALUES" ]]; then
  echo "missing render values: ${SERVER_VALUES}" >&2
  exit 1
fi
if [[ ! -f "$OPERATOR_VALUES" ]]; then
  echo "missing render values: ${OPERATOR_VALUES}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

tmp_server_rendered="${tmp_dir}/$(basename "$SERVER_RENDERED")"
tmp_operator_rendered="${tmp_dir}/$(basename "$OPERATOR_RENDERED")"

render_server "$tmp_server_rendered"
render_operator "$tmp_operator_rendered"

assert_no_helm_runtime_objects "$tmp_server_rendered"
assert_no_helm_runtime_objects "$tmp_operator_rendered"
EXPECTED_IMAGES=("${SERVER_EXPECTED_IMAGES[@]}")
assert_image_set "$tmp_server_rendered" >/dev/null
EXPECTED_IMAGES=("${OPERATOR_EXPECTED_IMAGES[@]}")
assert_image_set "$tmp_operator_rendered" >/dev/null
assert_crd_set "$tmp_operator_rendered" "${OPERATOR_EXPECTED_CRDS[@]}" >/dev/null

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  if cmp -s "$tmp_server_rendered" "$SERVER_RENDERED" && cmp -s "$tmp_operator_rendered" "$OPERATOR_RENDERED"; then
    echo "Infisical manifests are current."
    EXPECTED_IMAGES=("${SERVER_EXPECTED_IMAGES[@]}")
    assert_image_set "$tmp_server_rendered"
    EXPECTED_IMAGES=("${OPERATOR_EXPECTED_IMAGES[@]}")
    assert_image_set "$tmp_operator_rendered"
    assert_crd_set "$tmp_operator_rendered" "${OPERATOR_EXPECTED_CRDS[@]}"
    exit 0
  fi
  diff -u "$SERVER_RENDERED" "$tmp_server_rendered" || true
  diff -u "$OPERATOR_RENDERED" "$tmp_operator_rendered" || true
  echo "Infisical manifests are stale. Run infra/scripts/render-infisical-manifests.sh." >&2
  exit 1
fi

mkdir -p "$(dirname "$SERVER_RENDERED")"
mkdir -p "$(dirname "$OPERATOR_RENDERED")"
cp "$tmp_server_rendered" "$SERVER_RENDERED"
cp "$tmp_operator_rendered" "$OPERATOR_RENDERED"
echo "Rendered ${SERVER_RENDERED#"$REPO_ROOT"/}"
echo "Rendered ${OPERATOR_RENDERED#"$REPO_ROOT"/}"
EXPECTED_IMAGES=("${SERVER_EXPECTED_IMAGES[@]}")
assert_image_set "$SERVER_RENDERED"
EXPECTED_IMAGES=("${OPERATOR_EXPECTED_IMAGES[@]}")
assert_image_set "$OPERATOR_RENDERED"
assert_crd_set "$OPERATOR_RENDERED" "${OPERATOR_EXPECTED_CRDS[@]}"
