#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_ID="local"

usage() {
  cat <<'EOF'
Usage: delete-local-channel.sh [--channel local]

Deletes the local k3d platform cluster for a resolved local channel.

Options:
  --channel <id>  Channel id to resolve (default: local)
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
  if command -v python >/dev/null 2>&1; then
    command -v python
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    return 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_ID="$2"
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

main() {
  parse_args "$@"

  command -v k3d >/dev/null 2>&1 || die "k3d is required; run infra/scripts/install-cluster-tools.sh --install"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required to resolve channels"

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_ID")"

  local target
  local cluster_name
  local kubeconfig_path

  target="$(resolve_field target)"
  [[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"

  cluster_name="$(resolve_field cluster_name)"
  kubeconfig_path="$(resolve_field kubeconfig_path)"
  kubeconfig_path="${kubeconfig_path/#\~/$HOME}"

  if cluster_exists; then
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
