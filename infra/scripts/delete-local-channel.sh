#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
CHANNEL_ID=""

usage() {
  cat <<'EOF'
Usage: delete-local-channel.sh [--channel local]

Deletes the local k3d platform cluster for a resolved local channel.

Options:
  --channel <id>  Channel id to resolve (default: local); resolved JSON id is canonical
  -h, --help      Show this help
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
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
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
}

resolve_field() {
  local field="$1"

  "$PYTHON_BIN" - "$RESOLVED_JSON" "$field" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
field = sys.argv[2]

if field == "target":
    print(data["cluster"]["target"])
elif field == "id":
    print(data["id"])
elif field == "cluster_name":
    print(data["cluster"]["k3d"].get("cluster_name") or f"humility-{data['id']}")
elif field == "kubeconfig_path":
    print(data["cluster"].get("kubeconfig_path") or f"~/.kube/humility-{data['id']}.yaml")
else:
    raise SystemExit(f"unknown field: {field}")
PY
}

cluster_exists() {
  k3d cluster get "$cluster_name" >/dev/null 2>&1
}

delete_nested_app_clusters() {
  local nested_cluster="humility-${CHANNEL_ID}-app"

  if k3d cluster get "$nested_cluster" >/dev/null 2>&1; then
    log "Deleting nested app k3d cluster '${nested_cluster}'"
    k3d cluster delete "$nested_cluster"
  else
    log "nested app k3d cluster '${nested_cluster}' already gone"
  fi
}

cleanup_flux_resources() {
  if [[ ! -f "$kubeconfig_path" ]] || ! command -v kubectl >/dev/null 2>&1; then
    log "Skipping Flux cleanup because kubeconfig or kubectl is unavailable"
    return 0
  fi

  if ! kubectl --kubeconfig "$kubeconfig_path" get namespace kube-system >/dev/null 2>&1; then
    log "Skipping Flux cleanup because cluster API is unreachable"
    return 0
  fi

  log "Deleting Flux custom resources"
  kubectl --kubeconfig "$kubeconfig_path" delete kustomizations.kustomize.toolkit.fluxcd.io --all -A --ignore-not-found=true >/dev/null 2>&1 || true
  kubectl --kubeconfig "$kubeconfig_path" delete gitrepositories.source.toolkit.fluxcd.io --all -A --ignore-not-found=true >/dev/null 2>&1 || true

  if command -v flux >/dev/null 2>&1; then
    log "Uninstalling Flux controllers"
    KUBECONFIG="$kubeconfig_path" flux uninstall --silent >/dev/null 2>&1 || true
  else
    log "Skipping flux uninstall because flux CLI is unavailable"
  fi
}

main() {
  parse_args "$@"

  command -v k3d >/dev/null 2>&1 || die "k3d is required; run infra/scripts/install-cluster-tools.sh --install"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required to resolve channels"

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  local target
  local cluster_name
  local kubeconfig_path

  CHANNEL_ID="$(resolve_field id)"
  target="$(resolve_field target)"
  [[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"

  cluster_name="$(resolve_field cluster_name)"
  kubeconfig_path="$(resolve_field kubeconfig_path)"
  kubeconfig_path="${kubeconfig_path/#\~/$HOME}"

  if cluster_exists; then
    delete_nested_app_clusters
    cleanup_flux_resources
    log "Deleting k3d cluster '${cluster_name}'"
    k3d cluster delete "$cluster_name"
  else
    log "k3d cluster '${cluster_name}' already gone"
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    rm -f "$kubeconfig_path"
    log "Removed kubeconfig ${kubeconfig_path}"
  else
    log "kubeconfig ${kubeconfig_path} already absent"
  fi

  if cluster_exists; then
    die "k3d cluster '${cluster_name}' still exists after delete"
  fi

  log "Local channel '${CHANNEL_ID}' is deleted: cluster=${cluster_name}"
}

main "$@"
