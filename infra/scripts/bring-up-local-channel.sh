#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
TOOL_INSTALLER="${REPO_ROOT}/infra/scripts/install-cluster-tools.sh"
FLUX_INSTALLER="${REPO_ROOT}/infra/scripts/install-flux-for-channel.sh"
CHANNEL_REQUEST="local"
CHANNEL_ID=""
FORCE=0
REPAIR=0
CLUSTER_ONLY=0
RESEED_GITSERVER_ONLY=0
K3D_REGISTRY_PORT="${K3D_REGISTRY_PORT:-5000}"
REGISTRY_CONFIG_PATH=""

usage() {
  cat <<'EOF'
Usage: bring-up-local-channel.sh [--channel local] [--force | --repair] [--cluster-only] [--reseed-gitserver-only]

Creates the local k3d platform cluster for a resolved local channel and runs
the Flux post-install unless --cluster-only is passed. Use
--reseed-gitserver-only to update the existing in-cluster GitOps source from
the current worktree without running the full bootstrap sequence.

Environment:
  K3D_REGISTRY_PORT  Host port for the local k3d registry (default: 5000)

Options:
  --channel <id>   Channel id to resolve (default: local); resolved JSON id is canonical
  --force          Delete stale local state and recreate the cluster
  --repair         Repair stale generated kubeconfig state without recreating a matching cluster
  --cluster-only   Skip Flux post-install
  --reseed-gitserver-only
                   Reseed the existing in-cluster GitOps source only
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

cleanup_registry_config() {
  if [[ -n "$REGISTRY_CONFIG_PATH" ]]; then
    rm -f "$REGISTRY_CONFIG_PATH"
  fi
}

trap cleanup_registry_config EXIT

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
        CHANNEL_REQUEST="$2"
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
      --reseed-gitserver-only)
        RESEED_GITSERVER_ONLY=1
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

  if [[ "$FORCE" -eq 1 && "$REPAIR" -eq 1 ]]; then
    die "--force and --repair are mutually exclusive"
  fi
  if [[ "$RESEED_GITSERVER_ONLY" -eq 1 \
    && ( "$FORCE" -eq 1 || "$REPAIR" -eq 1 || "$CLUSTER_ONLY" -eq 1 ) ]]; then
    die "--reseed-gitserver-only is mutually exclusive with --force, --repair, and --cluster-only"
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
elif field == "id":
    print(data["id"])
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
elif field == "registry_mirrors":
    for mirror in data.get("image_registry", {}).get("pull_through_cache", {}).get("mirrors", []):
        print("\t".join([
            mirror["registry"],
            mirror["cache_name"],
            str(mirror["host_port"]),
            mirror["remote_url"],
        ]))
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
  awk 'BEGIN { bad = 0 } NF && $2 != "Ready" { bad = 1 } END { exit (bad || NR == 0) ? 1 : 0 }' <<<"$output"
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

cache_container_name() {
  local cache_name="$1"
  printf 'k3d-%s' "$cache_name"
}

local_registry_container_name() {
  printf 'k3d-%s' "$registry_name"
}

ensure_local_registry() {
  local container_name
  local volume_name

  [[ -n "$registry_name" && "$registry_name" != "null" && "$registry_name" != "None" ]] || return 0

  container_name="$(local_registry_container_name)"
  volume_name="${container_name}-data"

  if docker container inspect "$container_name" >/dev/null 2>&1; then
    if [[ "$(docker container inspect -f '{{.State.Running}}' "$container_name")" != "true" ]]; then
      log "Starting local image registry '${container_name}'"
      docker start "$container_name" >/dev/null
    else
      log "Local image registry '${container_name}' already exists"
    fi
    return 0
  fi

  log "Creating local image registry '${container_name}' on localhost:${K3D_REGISTRY_PORT}"
  docker volume create "$volume_name" >/dev/null
  docker run -d \
    --name "$container_name" \
    --restart unless-stopped \
    --publish "${K3D_REGISTRY_PORT}:5000" \
    --volume "${volume_name}:/var/lib/registry" \
    registry:2 >/dev/null
}

ensure_registry_cache() {
  local cache_name="$1"
  local host_port="$2"
  local remote_url="$3"
  local container_name
  local volume_name

  container_name="$(cache_container_name "$cache_name")"
  volume_name="k3d-${cache_name}-data"

  if docker container inspect "$container_name" >/dev/null 2>&1; then
    if [[ "$(docker container inspect -f '{{.State.Running}}' "$container_name")" != "true" ]]; then
      log "Starting registry cache '${container_name}'"
      docker start "$container_name" >/dev/null
    else
      log "Registry cache '${container_name}' already exists"
    fi
    return 0
  fi

  if k3d registry get "$container_name" >/dev/null 2>&1 || k3d registry get "$cache_name" >/dev/null 2>&1; then
    log "Registry cache '${container_name}' already exists"
    return 0
  fi

  log "Creating registry cache '${container_name}' for ${remote_url}"
  docker volume create "$volume_name" >/dev/null
  docker run -d \
    --name "$container_name" \
    --restart unless-stopped \
    --volume "${volume_name}:/var/lib/registry" \
    --env "REGISTRY_PROXY_REMOTEURL=${remote_url}" \
    --env "REGISTRY_STORAGE_DELETE_ENABLED=true" \
    registry:2 >/dev/null
}

ensure_registry_caches() {
  local registry
  local cache_name
  local host_port
  local remote_url
  local mirrors

  mirrors="$(resolve_field registry_mirrors)"
  [[ -n "$mirrors" ]] || return 0

  while IFS=$'\t' read -r registry cache_name host_port remote_url; do
    [[ -n "$registry" ]] || continue
    ensure_registry_cache "$cache_name" "$host_port" "$remote_url"
  done <<<"$mirrors"
}

write_registry_config() {
  local mirrors
  local registry
  local cache_name
  local host_port
  local remote_url

  mirrors="$(resolve_field registry_mirrors)"
  [[ -n "$mirrors" ]] || return 0

  REGISTRY_CONFIG_PATH="$(mktemp)"
  {
    echo "mirrors:"
    if [[ -n "$registry_name" && "$registry_name" != "null" && "$registry_name" != "None" ]]; then
      printf '  "%s:5000":\n' "$(local_registry_container_name)"
      printf '    endpoint:\n'
      printf '      - http://%s:5000\n' "$(local_registry_container_name)"
    fi
    while IFS=$'\t' read -r registry cache_name host_port remote_url; do
      [[ -n "$registry" ]] || continue
      printf '  "%s":\n' "$registry"
      printf '    endpoint:\n'
      printf '      - http://%s:5000\n' "$(cache_container_name "$cache_name")"
      printf '      - %s\n' "$remote_url"
    done <<<"$mirrors"
  } >"$REGISTRY_CONFIG_PATH"
}

connect_registry_caches_to_cluster_network() {
  local registry
  local cache_name
  local host_port
  local remote_url
  local mirrors
  local network_name="k3d-${cluster_name}"
  local container_name

  mirrors="$(resolve_field registry_mirrors)"
  [[ -n "$mirrors" ]] || return 0

  while IFS=$'\t' read -r registry cache_name host_port remote_url; do
    [[ -n "$registry" ]] || continue
    container_name="$(cache_container_name "$cache_name")"
    docker network inspect "$network_name" >/dev/null
    if docker container inspect -f "{{json .NetworkSettings.Networks}}" "$container_name" | grep -q "\"${network_name}\""; then
      log "Registry cache '${container_name}' already attached to ${network_name}"
    else
      log "Attaching registry cache '${container_name}' to ${network_name}"
      docker network connect "$network_name" "$container_name"
    fi
  done <<<"$mirrors"
}

connect_local_registry_to_cluster_network() {
  local network_name="k3d-${cluster_name}"
  local container_name

  [[ -n "$registry_name" && "$registry_name" != "null" && "$registry_name" != "None" ]] || return 0

  container_name="$(local_registry_container_name)"
  docker network inspect "$network_name" >/dev/null
  if docker container inspect -f "{{json .NetworkSettings.Networks}}" "$container_name" | grep -q "\"${network_name}\""; then
    log "Local image registry '${container_name}' already attached to ${network_name}"
  else
    log "Attaching local image registry '${container_name}' to ${network_name}"
    docker network connect "$network_name" "$container_name"
  fi
}

create_cluster() {
  local k3d_image_tag="${k3s_version/+/-}"
  local args=(
    cluster create "$cluster_name"
    --image "rancher/k3s:${k3d_image_tag}"
    --servers "$servers"
    --agents "$agents"
    --port "80:80@loadbalancer"
    --port "443:443@loadbalancer"
    --k3s-arg "--disable=traefik@server:0"
    --kubeconfig-update-default=false
    --volume "/var/run/docker.sock:/var/run/docker.sock@all"
    --wait
  )
  local registry
  local cache_name
  local host_port
  local remote_url

  ensure_local_registry
  ensure_registry_caches
  write_registry_config
  if [[ -n "$REGISTRY_CONFIG_PATH" ]]; then
    args+=(--registry-config "$REGISTRY_CONFIG_PATH")
  fi

  k3d "${args[@]}"
  connect_local_registry_to_cluster_network
  connect_registry_caches_to_cluster_network
  rm -f "$REGISTRY_CONFIG_PATH"
  REGISTRY_CONFIG_PATH=""
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
  distribute_step_ca_trust
  bootstrap_pomerium_oidc_application
}

reseed_gitserver_only() {
  [[ "$RESEED_GITSERVER_ONLY" -eq 1 ]] || return 0

  cluster_exists || die "--reseed-gitserver-only requires existing k3d cluster '${cluster_name}'"
  kubeconfig_matches_cluster || die "--reseed-gitserver-only requires kubeconfig '${kubeconfig_path}' to match k3d cluster '${cluster_name}'"

  verify_kubectl_reachability
  if ! verify_cluster_contract; then
    die "stale state detected: cluster '${cluster_name}' does not match channel topology: expected $((servers + agents)) Ready node(s)"
  fi

  log "Reseeding in-cluster GitOps source for local channel '${CHANNEL_ID}'"
  bash "$FLUX_INSTALLER" --channel "$CHANNEL_ID" --reseed-gitserver-only
  exit 0
}

# Copies step-ca's CA bundle (root + intermediate) into the auth-system
# namespace so Pomerium can trust the OIDC provider's TLS cert when fetching
# the OpenID discovery doc from auth.local.humility.local.
# Pomerium reads CERTIFICATE_AUTHORITY_FILE=/etc/pomerium/step-ca/ca.pem
# (mounted from the ConfigMap created here) at startup.
distribute_step_ca_trust() {
  local kubectl_args=(--kubeconfig "$kubeconfig_path")

  for attempt in $(seq 1 60); do
    if kubectl "${kubectl_args[@]}" -n step-ca-system get configmap step-ca-certs >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done

  if ! kubectl "${kubectl_args[@]}" -n step-ca-system get configmap step-ca-certs >/dev/null 2>&1; then
    log "step-ca-certs ConfigMap unavailable; skipping Pomerium step-ca trust copy"
    return 0
  fi

  if ! kubectl "${kubectl_args[@]}" get namespace auth-system >/dev/null 2>&1; then
    log "auth-system namespace not present; skipping Pomerium step-ca trust copy"
    return 0
  fi

  local root_ca intermediate_ca
  root_ca="$(kubectl "${kubectl_args[@]}" -n step-ca-system get configmap step-ca-certs -o 'jsonpath={.data.root_ca\.crt}')"
  intermediate_ca="$(kubectl "${kubectl_args[@]}" -n step-ca-system get configmap step-ca-certs -o 'jsonpath={.data.intermediate_ca\.crt}')"

  if [[ -z "$root_ca" || -z "$intermediate_ca" ]]; then
    log "step-ca-certs ConfigMap incomplete; skipping Pomerium step-ca trust copy"
    return 0
  fi

  local bundle_file
  bundle_file="$(mktemp)"
  printf '%s\n%s\n' "$intermediate_ca" "$root_ca" >"$bundle_file"

  log "Distributing step-ca trust bundle to auth-system/pomerium-step-ca-trust"
  kubectl "${kubectl_args[@]}" -n auth-system create configmap pomerium-step-ca-trust \
    --from-file=ca.pem="$bundle_file" \
    --dry-run=client -o yaml | kubectl "${kubectl_args[@]}" apply -f -

  rm -f "$bundle_file"

  if kubectl "${kubectl_args[@]}" -n auth-system get deployment pomerium-proxy >/dev/null 2>&1; then
    kubectl "${kubectl_args[@]}" -n auth-system rollout restart deployment/pomerium-proxy >/dev/null
    kubectl "${kubectl_args[@]}" -n auth-system rollout status deployment/pomerium-proxy --timeout=120s >/dev/null
  fi
}

# Creates the Authentik OAuth2 Provider + Application that Pomerium uses
# for OIDC. Runs from the host (not in-cluster) to avoid the Authentik
# server's IPv6-only listener that prevents pod-to-pod IPv4 reach.
# Reads the bootstrap token + client_id/secret from the authentik-config
# Secret (populated by InfisicalSecret).
bootstrap_pomerium_oidc_application() {
  local kubectl_args=(--kubeconfig "$kubeconfig_path")

  if ! kubectl "${kubectl_args[@]}" -n auth-system rollout status deployment/authentik-server --timeout=180s >/dev/null 2>&1; then
    log "authentik-server not ready; skipping Pomerium OIDC bootstrap"
    return 0
  fi

  local token client_id client_secret
  token="$(kubectl "${kubectl_args[@]}" -n auth-system get secret authentik-config -o 'jsonpath={.data.AUTHENTIK_BOOTSTRAP_TOKEN}' | base64 -d)"
  client_id="$(kubectl "${kubectl_args[@]}" -n auth-system get secret authentik-config -o 'jsonpath={.data.OIDC_CLIENT_ID}' | base64 -d)"
  client_secret="$(kubectl "${kubectl_args[@]}" -n auth-system get secret authentik-config -o 'jsonpath={.data.OIDC_CLIENT_SECRET}' | base64 -d)"

  if [[ -z "$token" || -z "$client_id" || -z "$client_secret" ]]; then
    log "missing OIDC bootstrap inputs; skipping Pomerium OIDC bootstrap"
    return 0
  fi

  local local_port="28085"
  local pf_log
  pf_log="$(mktemp)"
  kubectl "${kubectl_args[@]}" -n auth-system port-forward --address 127.0.0.1 svc/authentik-server "${local_port}:80" >"$pf_log" 2>&1 &
  local pf_pid=$!
  trap "kill $pf_pid 2>/dev/null; rm -f '$pf_log'" RETURN

  local ready=0
  for attempt in $(seq 1 30); do
    if curl -fsS -m 2 "http://127.0.0.1:${local_port}/-/health/ready/" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" != 1 ]]; then
    log "authentik port-forward did not become ready; skipping Pomerium OIDC bootstrap (see ${pf_log})"
    return 0
  fi

  local api="http://127.0.0.1:${local_port}/api/v3"
  local auth_h="Authorization: Bearer ${token}"

  local authz_flow authn_flow invalidation_flow signing_kp
  authz_flow="$(curl -fsS -H "$auth_h" "${api}/flows/instances/?slug=default-provider-authorization-implicit-consent" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"
  authn_flow="$(curl -fsS -H "$auth_h" "${api}/flows/instances/?slug=default-authentication-flow" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"
  invalidation_flow="$(curl -fsS -H "$auth_h" "${api}/flows/instances/?slug=default-provider-invalidation-flow" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"
  signing_kp="$(curl -fsS -H "$auth_h" "${api}/crypto/certificatekeypairs/?name=authentik+Self-signed+Certificate" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"

  if [[ -z "$authz_flow" || -z "$authn_flow" || -z "$invalidation_flow" || -z "$signing_kp" ]]; then
    log "missing default Authentik flows or signing keypair; skipping Pomerium OIDC bootstrap"
    return 0
  fi

  local scope_openid scope_email scope_profile
  scope_openid="$(curl -fsS -H "$auth_h" "${api}/propertymappings/provider/scope/?managed=goauthentik.io/providers/oauth2/scope-openid" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"
  scope_email="$(curl -fsS -H "$auth_h" "${api}/propertymappings/provider/scope/?managed=goauthentik.io/providers/oauth2/scope-email" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"
  scope_profile="$(curl -fsS -H "$auth_h" "${api}/propertymappings/provider/scope/?managed=goauthentik.io/providers/oauth2/scope-profile" | python3 -c 'import sys, json; print(next((r.get("pk", "") for r in json.load(sys.stdin).get("results", [])), ""))')"

  if [[ -z "$scope_openid" || -z "$scope_email" || -z "$scope_profile" ]]; then
    log "missing default Authentik scope mappings; skipping Pomerium OIDC bootstrap"
    return 0
  fi

  local provider_payload
  provider_payload="$(python3 -c "
import json, sys
print(json.dumps({
    'name': 'pomerium',
    'client_type': 'confidential',
    'client_id': sys.argv[1],
    'client_secret': sys.argv[2],
    'authorization_flow': sys.argv[3],
    'authentication_flow': sys.argv[4],
    'invalidation_flow': sys.argv[5],
    'signing_key': sys.argv[6],
    'redirect_uris': [{'matching_mode': 'strict', 'url': 'https://authenticate.local.humility.local/oauth2/callback'}],
    'sub_mode': 'hashed_user_id',
    'include_claims_in_id_token': True,
    'issuer_mode': 'per_provider',
    'property_mappings': [sys.argv[7], sys.argv[8], sys.argv[9]],
}))
" "$client_id" "$client_secret" "$authz_flow" "$authn_flow" "$invalidation_flow" "$signing_kp" "$scope_openid" "$scope_email" "$scope_profile")"

  local existing_provider
  existing_provider="$(curl -fsS -H "$auth_h" "${api}/providers/oauth2/?name=pomerium" | python3 -c 'import sys, json; r=json.load(sys.stdin).get("results", []); print(r[0].get("pk", "") if r else "")')"
  local provider_pk
  if [[ -n "$existing_provider" ]]; then
    log "Updating existing Authentik OAuth2Provider 'pomerium' (pk=${existing_provider})"
    curl -fsS -X PATCH -H "$auth_h" -H "Content-Type: application/json" -d "$provider_payload" "${api}/providers/oauth2/${existing_provider}/" >/dev/null
    provider_pk="$existing_provider"
  else
    log "Creating Authentik OAuth2Provider 'pomerium'"
    provider_pk="$(curl -fsS -X POST -H "$auth_h" -H "Content-Type: application/json" -d "$provider_payload" "${api}/providers/oauth2/" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("pk", ""))')"
  fi

  if [[ -z "$provider_pk" ]]; then
    log "failed to create or update OAuth2Provider; skipping Application step"
    return 0
  fi

  local app_payload
  app_payload="$(python3 -c "
import json, sys
print(json.dumps({
    'name': 'Pomerium',
    'slug': 'pomerium',
    'provider': int(sys.argv[1]),
    'policy_engine_mode': 'any',
    'meta_launch_url': 'https://protected-api.local.humility.local/',
}))
" "$provider_pk")"

  local existing_app
  existing_app="$(curl -fsS -H "$auth_h" "${api}/core/applications/?slug=pomerium" | python3 -c 'import sys, json; r=json.load(sys.stdin).get("results", []); print("yes" if r else "")')"
  if [[ "$existing_app" == "yes" ]]; then
    log "Updating existing Authentik Application 'pomerium'"
    curl -fsS -X PATCH -H "$auth_h" -H "Content-Type: application/json" -d "$app_payload" "${api}/core/applications/pomerium/" >/dev/null
  else
    log "Creating Authentik Application 'pomerium'"
    curl -fsS -X POST -H "$auth_h" -H "Content-Type: application/json" -d "$app_payload" "${api}/core/applications/" >/dev/null
  fi

  log "Pomerium OAuth2 Provider + Application reconciled in Authentik"
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

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  local target
  local cluster_name
  local k3s_version
  local servers
  local agents
  local registry_name
  local kubeconfig_path

  CHANNEL_ID="$(resolve_field id)"
  target="$(resolve_field target)"
  [[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"

  cluster_name="$(resolve_field cluster_name)"
  k3s_version="$(resolve_field k3s_version)"
  servers="$(resolve_field servers)"
  agents="$(resolve_field agents)"
  registry_name="$(resolve_field registry_name)"
  kubeconfig_path="$(resolve_field kubeconfig_path)"
  kubeconfig_path="${kubeconfig_path/#\~/$HOME}"

  reseed_gitserver_only

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
