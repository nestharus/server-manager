#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
TOOL_INSTALLER="${REPO_ROOT}/infra/scripts/install-cluster-tools.sh"
FLUX_INSTALLER="${REPO_ROOT}/infra/scripts/install-flux-for-channel.sh"
CHANNEL_ID="local"
FORCE=0
REPAIR=0
CLUSTER_ONLY=0
POSITIONAL_CHANNEL=0

usage() {
  cat <<'EOF'
Usage: bring-up-local-channel.sh [local | --channel local] [--force | --repair] [--cluster-only]

Creates the local k3d platform cluster for a resolved local channel and runs
the Flux post-install unless --cluster-only is passed.

Options:
  --channel <id>   Channel id to resolve (default: local)
  --force          Delete stale local state and recreate the cluster
  --repair         Repair stale generated kubeconfig state without recreating a matching cluster
  --cluster-only   Skip Flux post-install
  -h, --help       Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

stale_state() {
  die "stale state detected: $*; rerun with --repair to fix generated kubeconfig state or --force to recreate the local cluster"
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
        CHANNEL_ID="$2"
        shift
        ;;
      --force)
        FORCE=1
        ;;
      --repair)
        REPAIR=1
        ;;
      --cluster-only)
        CLUSTER_ONLY=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        if [[ "$1" == -* || "$POSITIONAL_CHANNEL" -eq 1 ]]; then
          die "unknown argument: $1"
        fi
        CHANNEL_ID="$1"
        POSITIONAL_CHANNEL=1
        ;;
    esac
    shift
  done

  if [[ "$FORCE" -eq 1 && "$REPAIR" -eq 1 ]]; then
    die "--force and --repair are mutually exclusive"
  fi
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

cluster_exists() {
  k3d cluster get "$cluster_name" >/dev/null 2>&1
}

write_kubeconfig() {
  mkdir -p "$(dirname "$kubeconfig_path")"
  k3d kubeconfig get "$cluster_name" > "$kubeconfig_path"
  chmod 600 "$kubeconfig_path"
  log "Wrote kubeconfig to ${kubeconfig_path}"
}

kubeconfig_matches_cluster() {
  local expected

  [[ -f "$kubeconfig_path" ]] || return 1

  expected="$(mktemp)"
  k3d kubeconfig get "$cluster_name" > "$expected"
  if cmp -s "$expected" "$kubeconfig_path"; then
    rm -f "$expected"
    return 0
  fi

  rm -f "$expected"
  return 1
}

node_count() {
  local output

  if ! output="$(kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null)"; then
    echo 0
    return 0
  fi

  awk 'NF { count += 1 } END { print count + 0 }' <<<"$output"
}

all_nodes_ready() {
  local output

  output="$(kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null)" || return 1
  awk 'NF && $2 != "Ready" { bad = 1 } END { exit bad }' <<<"$output"
}

verify_kubectl_reachability() {
  local count

  count="$(node_count)"
  [[ "$count" -ge 1 ]] || die "kubectl could not reach any nodes through ${kubeconfig_path}"
}

verify_cluster_contract() {
  local expected_count
  local actual_count

  expected_count=$((servers + agents))
  actual_count="$(node_count)"

  if [[ "$actual_count" -ne "$expected_count" ]]; then
    return 1
  fi

  all_nodes_ready
}

delete_existing_state() {
  if cluster_exists; then
    log "Deleting existing k3d cluster '${cluster_name}' before recreate"
    k3d cluster delete "$cluster_name"
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    rm -f "$kubeconfig_path"
    log "Removed stale kubeconfig ${kubeconfig_path}"
  fi
}

create_cluster() {
  local k3d_image_tag="${k3s_version/+/-}"
  local args=(
    cluster create "$cluster_name"
    --image "rancher/k3s:${k3d_image_tag}"
    --servers "$servers"
    --agents "$agents"
    --kubeconfig-update-default=false
    --wait
  )

  if [[ -n "$registry_name" && "$registry_name" != "null" && "$registry_name" != "None" ]]; then
    args+=(--registry-create "$registry_name")
  fi

  k3d "${args[@]}"
  write_kubeconfig
  verify_kubectl_reachability

  if ! verify_cluster_contract; then
    die "created cluster '${cluster_name}' does not match channel topology: expected $((servers + agents)) Ready node(s)"
  fi

  log "Local channel '${CHANNEL_ID}' is up: cluster=${cluster_name} kubeconfig=${kubeconfig_path}"
}

install_flux_post_install() {
  if [[ "$CLUSTER_ONLY" -eq 1 ]]; then
    log "Skipping Flux post-install because --cluster-only was passed"
    return 0
  fi

  bash "$FLUX_INSTALLER" --channel "$CHANNEL_ID"
}

main() {
  parse_args "$@"

  command -v k3d >/dev/null 2>&1 || die "k3d is required; run infra/scripts/install-cluster-tools.sh --install"
  command -v docker >/dev/null 2>&1 || die "docker is required to run k3d"
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required to verify local cluster reachability"
  if [[ "$CLUSTER_ONLY" -eq 0 ]]; then
    bash "$TOOL_INSTALLER" --check --no-color >/dev/null || die "local GitOps toolchain must match pinned versions; run infra/scripts/install-cluster-tools.sh --install"
  fi
  docker info >/dev/null 2>&1 || die "docker daemon is unavailable"
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

  if [[ "$FORCE" -eq 1 ]]; then
    delete_existing_state
    create_cluster
    install_flux_post_install
    exit 0
  fi

  if cluster_exists; then
    if ! kubeconfig_matches_cluster; then
      if [[ "$REPAIR" -eq 1 ]]; then
        log "Repairing kubeconfig for existing k3d cluster '${cluster_name}'"
        write_kubeconfig
      else
        stale_state "cluster '${cluster_name}' exists but kubeconfig '${kubeconfig_path}' is missing or does not match k3d output"
      fi
    fi

    verify_kubectl_reachability

    if ! verify_cluster_contract; then
      die "stale state detected: cluster '${cluster_name}' does not match channel topology: expected $((servers + agents)) Ready node(s); rerun with --force to recreate it"
    fi

    if [[ "$REPAIR" -eq 1 ]]; then
      log "Local channel '${CHANNEL_ID}' repaired and already up: cluster=${cluster_name} kubeconfig=${kubeconfig_path}"
    else
      log "Local channel '${CHANNEL_ID}' already up: cluster=${cluster_name} kubeconfig=${kubeconfig_path}"
    fi
    install_flux_post_install
    exit 0
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    if [[ "$REPAIR" -eq 1 ]]; then
      rm -f "$kubeconfig_path"
      log "Removed stale kubeconfig ${kubeconfig_path}"
    else
      stale_state "kubeconfig '${kubeconfig_path}' exists but k3d cluster '${cluster_name}' does not"
    fi
  fi

  if [[ "$REPAIR" -eq 1 ]]; then
    log "Repair requested; creating missing k3d cluster '${cluster_name}'"
  fi

  create_cluster
  install_flux_post_install
}

main "$@"
