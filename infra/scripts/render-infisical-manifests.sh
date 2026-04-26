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

EXPECTED_IMAGES=(
  "infisical/infisical:v0.151.0"
  "mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16"
  "mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18"
)

CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: render-infisical-manifests.sh [--check]

Renders the pinned Infisical standalone Helm chart to committed raw manifests.

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

  helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" >/dev/null
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


documents = [doc for doc in yaml.safe_load_all(raw_path.read_text(encoding="utf-8")) if doc]
for document in documents:
    strip_metadata(document)

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

assert_no_helm_runtime_objects() {
  local path="$1"
  if grep -Eq '^[[:space:]]*kind:[[:space:]]*(HelmRelease|OCIRepository)[[:space:]]*$' "$path"; then
    echo "rendered manifests contain HelmRelease or OCIRepository: ${path}" >&2
    exit 1
  fi
}

assert_image_set() {
  local path="$1"
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

require_command helm
if ! PYTHON_BIN="$(python_bin)"; then
  echo "missing required command: python or python3" >&2
  exit 1
fi

if [[ ! -f "$SERVER_VALUES" ]]; then
  echo "missing render values: ${SERVER_VALUES}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

tmp_rendered="${tmp_dir}/$(basename "$SERVER_RENDERED")"
render_server "$tmp_rendered"
assert_no_helm_runtime_objects "$tmp_rendered"
assert_image_set "$tmp_rendered" >/dev/null

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  if cmp -s "$tmp_rendered" "$SERVER_RENDERED"; then
    echo "Infisical server manifests are current."
    assert_image_set "$tmp_rendered"
    exit 0
  fi
  diff -u "$SERVER_RENDERED" "$tmp_rendered" || true
  echo "Infisical server manifests are stale. Run infra/scripts/render-infisical-manifests.sh." >&2
  exit 1
fi

mkdir -p "$(dirname "$SERVER_RENDERED")"
cp "$tmp_rendered" "$SERVER_RENDERED"
echo "Rendered ${SERVER_RENDERED#"$REPO_ROOT"/}"
assert_image_set "$SERVER_RENDERED"
