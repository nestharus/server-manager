#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
BUILDER="${REPO_ROOT}/infra/scripts/build-channel-image.sh"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
IMAGE_TAG=""
KEEP=0
CLUSTER_MODE=0

usage() {
  cat <<'EOF'
Usage: validate_container_delivery_local.sh [--cluster] [--channel local] [--kubeconfig PATH] [--tag TAG] [--keep]

Builds the INIT-108 registry-smoke image, pushes it to the local k3d registry,
and runs a Pod that pulls the image through the cluster registry endpoint.

Options:
  --cluster          Run explicit cluster runtime validation
  --channel <id>     Channel id to resolve (default: local)
  --kubeconfig PATH  Kubeconfig for the local k3d channel
  --tag TAG          Override the channel sample tag
  --keep             Keep the smoke namespace and Pod after success
  -h, --help         Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cluster)
        CLUSTER_MODE=1
        ;;
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift
        ;;
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift
        ;;
      --keep)
        KEEP=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
    shift
  done
}

json_field() {
  local field="$1"

  "$PYTHON_BIN" - "$RESOLVED_JSON" "$field" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
field = sys.argv[2]
registry = data["image_registry"]

if field == "id":
    print(data["id"])
elif field == "app":
    print(registry["sample"]["app"])
elif field == "tag":
    print(registry["sample"]["tag"])
elif field == "namespace":
    print(registry["sample"]["namespace"])
elif field == "pull_url":
    print(registry["pull_url"])
elif field == "repository_prefix":
    print(registry["repository_prefix"])
else:
    raise SystemExit(f"unknown field: {field}")
PY
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

cleanup() {
  if [[ "$KEEP" -eq 0 && -n "${NAMESPACE:-}" ]]; then
    kubectl_cmd delete namespace "$NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

main() {
  parse_args "$@"

  command -v docker >/dev/null 2>&1 || die "docker is required"
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  if [[ "$CLUSTER_MODE" -eq 1 ]]; then
    log "Cluster runtime mode requested"
  fi
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  local channel_id
  local app_name
  local tag
  local pull_url
  local repository_prefix
  local pull_image
  local build_output

  channel_id="$(json_field id)"
  app_name="$(json_field app)"
  tag="${IMAGE_TAG:-$(json_field tag)}"
  NAMESPACE="$(json_field namespace)"
  pull_url="$(json_field pull_url)"
  repository_prefix="$(json_field repository_prefix)"
  pull_image="${pull_url}/${repository_prefix}/${app_name}:${tag}"

  log "Building and pushing ${channel_id}/${app_name}:${tag}"
  build_output="$("$BUILDER" \
    --channel "$channel_id" \
    --app "$app_name" \
    --tag "$tag" \
    --context "${REPO_ROOT}/containers/samples/${app_name}" \
    --file "${REPO_ROOT}/containers/samples/${app_name}/Containerfile")"
  printf '%s\n' "$build_output"

  kubectl_cmd create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl_cmd apply -f - >/dev/null
  kubectl_cmd label namespace "$NAMESPACE" \
    pod-security.kubernetes.io/enforce=restricted \
    pod-security.kubernetes.io/warn=restricted \
    pod-security.kubernetes.io/audit=restricted \
    --overwrite >/dev/null

  log "Running Pod/${app_name} from ${pull_image}"
  kubectl_cmd -n "$NAMESPACE" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${app_name}
  labels:
    app.kubernetes.io/name: ${app_name}
    platform.humility.gg/init: "108"
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: ${app_name}
      image: ${pull_image}
      imagePullPolicy: Always
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
        readOnlyRootFilesystem: true
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      resources:
        requests:
          cpu: 10m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 64Mi
YAML

  kubectl_cmd -n "$NAMESPACE" wait "pod/${app_name}" --for=condition=Ready --timeout=120s >/dev/null
  if kubectl_cmd -n "$NAMESPACE" logs "pod/${app_name}" | grep -q "INIT-108 registry smoke container running"; then
    log "PASS: image push, Pod pull, and container run verified for ${pull_image}"
  else
    kubectl_cmd -n "$NAMESPACE" describe "pod/${app_name}" || true
    die "registry smoke container log marker missing"
  fi
}

main "$@"
