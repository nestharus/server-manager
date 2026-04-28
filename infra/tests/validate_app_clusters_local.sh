#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
CLUSTER_MODE=0
CLAIM_NAMESPACE="platform-app-clusters"
CLAIM_NAME="local-sample"
APP_CLUSTER_NAME="humility-local-app"

usage() {
  cat <<'EOF'
Usage: validate_app_clusters_local.sh [--cluster] [--kubeconfig PATH]

Validates the INIT-106 local Crossplane app-cluster proof against an existing
local channel: Crossplane controllers available, provider packages healthy,
AppCluster/local-sample Ready=True, and nested k3d app cluster running.

Options:
  --cluster          Run explicit cluster runtime validation
  --kubeconfig PATH  Kubeconfig for the local k3d channel
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)
      CLUSTER_MODE=1
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift
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

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

wait_json_condition() {
  local description="$1"
  local command_json="$2"
  local condition_type="$3"
  local attempts="${4:-160}"
  local attempt
  local payload

  for attempt in $(seq 1 "$attempts"); do
    payload="$(eval "$command_json" 2>/dev/null || true)"
    if python3 -c '
import json
import sys

condition_type = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") != condition_type:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)
raise SystemExit(1)
' "$condition_type" <<<"$payload"
    then
      return 0
    fi
    sleep 3
  done

  echo "Timed out waiting for ${description}" >&2
  return 1
}

require_command kubectl
require_command python3
require_command k3d
if [[ "$CLUSTER_MODE" -eq 1 ]]; then
  log "Cluster runtime mode requested"
fi
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl_cmd -n crossplane-system wait deployment/crossplane --for=condition=Available --timeout=300s >/dev/null
kubectl_cmd -n crossplane-system wait deployment/crossplane-rbac-manager --for=condition=Available --timeout=300s >/dev/null
log "PASS: Crossplane Deployments Available"

wait_json_condition \
  "Provider/provider-kubernetes Healthy" \
  "kubectl_cmd get provider.pkg.crossplane.io provider-kubernetes -o json" \
  "Healthy"
log "PASS: Provider/provider-kubernetes Healthy=True"

wait_json_condition \
  "Provider/provider-vultr Healthy" \
  "kubectl_cmd get provider.pkg.crossplane.io provider-vultr -o json" \
  "Healthy"
log "PASS: Provider/provider-vultr Healthy=True"

wait_json_condition \
  "AppCluster/${CLAIM_NAME} Ready" \
  "kubectl_cmd -n ${CLAIM_NAMESPACE} get appcluster.platform.humility.gg ${CLAIM_NAME} -o json" \
  "Ready" \
  240
log "PASS: AppCluster/${CLAIM_NAME} Ready=True"

if k3d cluster get "$APP_CLUSTER_NAME" >/dev/null 2>&1; then
  log "PASS: nested k3d cluster ${APP_CLUSTER_NAME} exists"
else
  die "nested k3d cluster ${APP_CLUSTER_NAME} is missing"
fi

tmp_kubeconfig="$(mktemp)"
trap 'rm -f "$tmp_kubeconfig"' EXIT
k3d kubeconfig get "$APP_CLUSTER_NAME" >"$tmp_kubeconfig"
kubectl --kubeconfig "$tmp_kubeconfig" wait nodes --all --for=condition=Ready --timeout=180s >/dev/null
log "PASS: nested k3d cluster ${APP_CLUSTER_NAME} nodes Ready"
