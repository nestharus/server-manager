#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_ID="local"
RECREATE=0

usage() {
  cat <<'EOF'
Usage: bring-up-local-channel.sh [--channel local] [--recreate]

Creates the local k3d platform cluster for a resolved local channel.

Options:
  --channel <id>  Channel id to resolve (default: local)
  --recreate      Delete an existing cluster before creating it again
  -h, --help      Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
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
      --recreate)
        RECREATE=1
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
elif field == "k3s_version":
    print(data["cluster"]["k3s_version"])
elif field == "servers":
    print(data["cluster"]["k3d"]["servers"])
elif field == "agents":
    print(data["cluster"]["k3d"]["agents"])
elif field == "registry_name":
    print(data["cluster"]["k3d"]["registry_name"])
elif field == "kubeconfig_path":
    print(data["cluster"].get("kubeconfig_path") or f"~/.kube/humility-{data['id']}.yaml")
else:
    raise SystemExit(f"unknown field: {field}")
PY
}

main() {
  parse_args "$@"

  command -v k3d >/dev/null 2>&1 || die "k3d is required; run infra/scripts/install-cluster-tools.sh --install"
  command -v docker >/dev/null 2>&1 || die "docker is required to run k3d"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required to resolve channels"

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_ID")"

  local target
  local cluster_name
  local k3s_version
  local servers
  local agents
  local registry_name
  local kubeconfig_path

  target="$(resolve_field target)"
  [[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"

  cluster_name="$(resolve_field cluster_name)"
  k3s_version="$(resolve_field k3s_version)"
  servers="$(resolve_field servers)"
  agents="$(resolve_field agents)"
  registry_name="$(resolve_field registry_name)"
  kubeconfig_path="$(resolve_field kubeconfig_path)"
  kubeconfig_path="${kubeconfig_path/#\~/$HOME}"

  if k3d cluster get "$cluster_name" >/dev/null 2>&1; then
    if [[ "$RECREATE" -eq 0 ]]; then
      echo "k3d cluster '${cluster_name}' exists; skipping create"
      mkdir -p "$(dirname "$kubeconfig_path")"
      k3d kubeconfig get "$cluster_name" > "$kubeconfig_path"
      chmod 600 "$kubeconfig_path"
      echo "Wrote kubeconfig to ${kubeconfig_path}"
      exit 0
    fi

    echo "Deleting existing k3d cluster '${cluster_name}' before recreate"
    k3d cluster delete "$cluster_name"
  fi

  mkdir -p "$(dirname "$kubeconfig_path")"

  k3d cluster create "$cluster_name" \
    --image "rancher/k3s:${k3s_version}" \
    --servers "$servers" \
    --agents "$agents" \
    --registry-create "${registry_name}:0.0.0.0:5000" \
    --kubeconfig-update-default=false \
    --wait

  k3d kubeconfig get "$cluster_name" > "$kubeconfig_path"
  chmod 600 "$kubeconfig_path"
  echo "Wrote kubeconfig to ${kubeconfig_path}"
}

main "$@"
