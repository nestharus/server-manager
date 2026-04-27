#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

CHANNEL_REQUEST="local"
KUBECONFIG_ARG=()
LOCAL_PORT="18085"

SERVER_NAMESPACE="infisical-system"
SERVER_DEPLOYMENT="infisical-infisical-standalone-infisical"
SERVER_SERVICE="infisical"
POSTGRES_STATEFULSET="postgresql"
REDIS_STATEFULSET="redis-master"
BOOTSTRAP_SECRET_NAME="infisical-server-bootstrap"

ORG_NAME="platform"
PROJECT_SLUG="server-manager"
PROJECT_NAME="server-manager"
PROJECT_ID=""
ORG_ID=""
ENVIRONMENT_SLUG="local"
ENVIRONMENT_NAME="local"
SECRETS_PATH="/runtime/local"
IDENTITY_NAME="local-operator"

UA_SECRET_NAME="infisical-operator-auth"
UA_SECRET_NAMESPACE="infisical-system"
TEMP_FILES=()
PORT_FORWARD_PID=""

usage() {
  cat <<'EOF'
Usage: bootstrap-infisical-server-manager.sh [--channel local] [--kubeconfig PATH] [--local-port PORT]

Bootstraps the local server-manager runtime secret path after INIT-113:
  - verifies the existing Secret/infisical-operator-auth Universal Auth Secret
  - creates or finds project server-manager and environment local
  - creates or finds /runtime/local
  - seeds DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, and SUPABASE_SERVICE_KEY only if absent
  - grants the existing local-operator Machine Identity access to server-manager

If DISCORD_BOT_TOKEN is not supplied, a synthetic token is stored for local E2E.
The local Discord deployment runs with DISCORD_DRY_RUN=1, so the synthetic token
is never used to connect to Discord. This script never writes secret values to Git
or stdout.
EOF
}

log() {
  printf '%s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

stop_port_forward() {
  if [[ -n "${PORT_FORWARD_PID:-}" ]] && kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  stop_port_forward
  if [[ ${#TEMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]}"
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || die "--channel requires a value"
      CHANNEL_REQUEST="$2"
      shift 2
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_ARG=(--kubeconfig "$2")
      shift 2
      ;;
    --local-port)
      [[ $# -ge 2 ]] || die "--local-port requires a value"
      LOCAL_PORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

kubectl_cmd() {
  if [[ ${#KUBECONFIG_ARG[@]} -gt 0 ]]; then
    kubectl "${KUBECONFIG_ARG[@]}" "$@"
  else
    kubectl "$@"
  fi
}

urlencode() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

secret_value() {
  local key="$1"
  local value
  value="$(kubectl_cmd -n "$SERVER_NAMESPACE" get secret "$BOOTSTRAP_SECRET_NAME" -o "jsonpath={.data.${key}}" | base64 -d)"
  [[ -n "$value" ]] || die "Secret/${BOOTSTRAP_SECRET_NAME} key ${key} is empty"
  printf '%s' "$value"
}

operator_ua_secret_value() {
  local key="$1"
  kubectl_cmd -n "$UA_SECRET_NAMESPACE" get secret "$UA_SECRET_NAME" -o "jsonpath={.data.${key}}" 2>/dev/null | base64 -d || true
}

verify_operator_ua_secret() {
  [[ -n "$(operator_ua_secret_value clientId)" ]] || die "Secret/${UA_SECRET_NAME} key clientId is empty or missing"
  [[ -n "$(operator_ua_secret_value clientSecret)" ]] || die "Secret/${UA_SECRET_NAME} key clientSecret is empty or missing"
  ORG_ID="$(operator_ua_secret_value organizationId)"
  [[ -n "$ORG_ID" ]] || die "Secret/${UA_SECRET_NAME} key organizationId is empty or missing"
}

resolve_channel_runtime() {
  local resolved
  resolved="$(mktemp)"
  TEMP_FILES+=("$resolved")
  python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$CHANNEL_REQUEST" --out "$resolved" >/dev/null

  ENVIRONMENT_SLUG="$(jq -er '.infisical.environment' "$resolved")"
  ENVIRONMENT_NAME="$ENVIRONMENT_SLUG"
  UA_SECRET_NAME="$(jq -er '.infisical.universal_auth_secret_name' "$resolved")"
  UA_SECRET_NAMESPACE="$(jq -er '.infisical.universal_auth_secret_namespace' "$resolved")"
  SERVER_NAMESPACE="$(jq -er '.infisical.operator_namespace' "$resolved")"
}

wait_for_server() {
  log "Waiting for Infisical server dependencies in namespace ${SERVER_NAMESPACE}"
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${POSTGRES_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${REDIS_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "deployment/${SERVER_DEPLOYMENT}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" wait "deployment/${SERVER_DEPLOYMENT}" --for=condition=Available --timeout=300s >/dev/null
}

start_port_forward() {
  local log_file="${REPO_ROOT}/.tmp/infisical-server-manager-port-forward.log"
  mkdir -p "${REPO_ROOT}/.tmp"
  : >"$log_file"
  kubectl_cmd -n "$SERVER_NAMESPACE" port-forward --address 127.0.0.1 "service/${SERVER_SERVICE}" "${LOCAL_PORT}:8080" >"$log_file" 2>&1 &
  PORT_FORWARD_PID="$!"

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/api/status" >/dev/null 2>&1; then
      return
    fi
    if ! kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
      die "kubectl port-forward exited early; see ${log_file}"
    fi
    sleep 1
  done

  die "Infisical API did not become reachable on localhost:${LOCAL_PORT}; see ${log_file}"
}

bootstrap_or_login() {
  local api_url="$1"
  local admin_email="$2"
  local admin_password="$3"
  local bootstrap_output
  local token
  local org_id

  set +e
  bootstrap_output="$(
    infisical bootstrap \
      --domain "$api_url" \
      --email "$admin_email" \
      --password "$admin_password" \
      --organization "$ORG_NAME" \
      --ignore-if-bootstrapped \
      --output json \
      --silent 2>/dev/null
  )"
  set -e

  token="$(jq -er '.identity.credentials.token // empty' <<<"$bootstrap_output" 2>/dev/null || true)"
  if [[ -n "$token" ]]; then
    org_id="$(jq -er '.organization.id // empty' <<<"$bootstrap_output" 2>/dev/null || true)"
    [[ -n "$org_id" ]] || die "Infisical bootstrap response did not include organization.id"
    printf '%s\t%s' "$token" "$org_id"
    return
  fi

  [[ -n "${ORG_ID:-}" ]] || die "Infisical is already bootstrapped but organization id is unknown"
  token="$(
    infisical login \
      --method user \
      --email "$admin_email" \
      --password "$admin_password" \
      --organization-id "$ORG_ID" \
      --domain "${api_url}/api" \
      --plain \
      --silent 2>/dev/null
  )"
  [[ -n "$token" ]] || die "unable to obtain Infisical admin token"
  printf '%s\t%s' "$token" "$ORG_ID"
}

api_request() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local response_file
  local status

  response_file="$(mktemp)"
  TEMP_FILES+=("$response_file")
  if [[ -n "$body" ]]; then
    status="$(curl -sS -o "$response_file" -w '%{http_code}' -X "$method" "http://127.0.0.1:${LOCAL_PORT}${path}" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$body")"
  else
    status="$(curl -sS -o "$response_file" -w '%{http_code}' -X "$method" "http://127.0.0.1:${LOCAL_PORT}${path}" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}")"
  fi

  if [[ "$status" =~ ^2 ]]; then
    cat "$response_file"
    rm -f "$response_file"
    return 0
  fi
  if [[ "$status" == "404" ]]; then
    rm -f "$response_file"
    return 4
  fi

  log "Infisical API ${method} ${path} returned HTTP ${status}"
  sed 's/clientSecret[^,}]*/clientSecret:redacted/g' "$response_file" >&2 || true
  rm -f "$response_file"
  return 1
}

find_or_create_project() {
  local project
  local body
  local org_id="${ORG_ID:-}"
  local status

  set +e
  project="$(api_request GET "/api/v1/projects/slug/${PROJECT_SLUG}")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    printf '%s\t%s' "$(jq -er '.project.id // .id' <<<"$project")" "$(jq -er '.project.orgId // .orgId // empty' <<<"$project")"
    return
  fi
  [[ "$status" -eq 4 ]] || return "$status"
  [[ -n "$org_id" ]] || die "organization id is required to create project ${PROJECT_SLUG}"

  body="$(jq -n --arg name "$PROJECT_NAME" --arg slug "$PROJECT_SLUG" --arg org_id "$org_id" \
    '{projectName: $name, projectDescription: "Humility server-manager runtime secrets", slug: $slug, organizationId: $org_id, template: "default", type: "secret-manager", shouldCreateDefaultEnvs: false, hasDeleteProtection: true}')"
  project="$(api_request POST "/api/v1/projects" "$body")"
  printf '%s\t%s' "$(jq -er '.project.id // .id' <<<"$project")" "$(jq -er '.project.orgId // .orgId' <<<"$project")"
}

ensure_environment() {
  local project
  local exists
  local body

  project="$(api_request GET "/api/v1/projects/slug/${PROJECT_SLUG}")"
  exists="$(jq -er --arg slug "$ENVIRONMENT_SLUG" '(.project.environments // .environments // [])[]? | select(.slug == $slug) | .id' <<<"$project" 2>/dev/null || true)"
  [[ -n "$exists" ]] && return

  body="$(jq -n --arg name "$ENVIRONMENT_NAME" --arg slug "$ENVIRONMENT_SLUG" '{name: $name, slug: $slug, position: 1}')"
  api_request POST "/api/v1/workspace/${PROJECT_ID}/environments" "$body" >/dev/null
}

ensure_secret_folder() {
  local normalized="${SECRETS_PATH#/}"
  local current="/"
  local segment
  local parent_path
  local encoded_path
  local folders
  local exists
  local body

  normalized="${normalized%/}"
  [[ -n "$normalized" ]] || return
  IFS='/' read -r -a segments <<<"$normalized"
  for segment in "${segments[@]}"; do
    parent_path="$current"
    encoded_path="$(urlencode "$parent_path")"
    folders="$(api_request GET "/api/v2/folders?projectId=${PROJECT_ID}&environment=${ENVIRONMENT_SLUG}&path=${encoded_path}&recursive=false")"
    exists="$(jq -er --arg name "$segment" '.folders[]? | select(.name == $name) | .id' <<<"$folders" 2>/dev/null || true)"
    if [[ -z "$exists" ]]; then
      body="$(jq -n \
        --arg project_id "$PROJECT_ID" \
        --arg environment "$ENVIRONMENT_SLUG" \
        --arg name "$segment" \
        --arg path "$parent_path" \
        '{projectId: $project_id, environment: $environment, name: $name, path: $path}')"
      api_request POST "/api/v2/folders" "$body" >/dev/null
    fi
    [[ "$current" == "/" ]] && current="/${segment}" || current="${current}/${segment}"
  done
}

find_identity() {
  local identities
  local body
  body="$(jq -n --arg name "$IDENTITY_NAME" '{limit: 100, search: {name: {"$eq": $name}}}')"
  identities="$(api_request POST "/api/v1/identities/search" "$body")"
  jq -er --arg name "$IDENTITY_NAME" '.identities[]? | select((.name // .identity.name) == $name) | (.identity.id // .identityId // .id)' <<<"$identities"
}

ensure_identity_project_membership() {
  local identity_id="$1"
  local membership
  local status
  local body

  set +e
  membership="$(api_request GET "/api/v2/workspace/${PROJECT_ID}/identity-memberships/${identity_id}")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    return
  fi
  [[ "$status" -eq 4 ]] || return "$status"

  body="$(jq -n '{roles: [{role: "admin"}]}')"
  api_request POST "/api/v2/workspace/${PROJECT_ID}/identity-memberships/${identity_id}" "$body" >/dev/null
}

secret_exists() {
  local name="$1"
  local secret_path="${SECRETS_PATH%/}"
  local value
  value="$(infisical secrets get "$name" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$secret_path" \
    --plain \
    --silent 2>/dev/null || true)"
  [[ -n "$value" ]]
}

set_secret_if_absent() {
  local name="$1"
  local value="$2"
  local secret_path="${SECRETS_PATH%/}"

  if secret_exists "$name"; then
    return
  fi
  infisical secrets set "${name}=${value}" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$secret_path" \
    --silent >/dev/null
}

prepare_project_path() {
  PROJECT_SLUG="$1"
  PROJECT_NAME="$PROJECT_SLUG"
  ENVIRONMENT_SLUG="$2"
  ENVIRONMENT_NAME="$ENVIRONMENT_SLUG"
  SECRETS_PATH="$3"

  PROJECT_RESULT="$(find_or_create_project)"
  PROJECT_ID="${PROJECT_RESULT%%$'\t'*}"
  PROJECT_ORG_ID="${PROJECT_RESULT#*$'\t'}"
  if [[ -n "$PROJECT_ORG_ID" ]]; then
    ORG_ID="$PROJECT_ORG_ID"
  fi

  ensure_environment
  ensure_secret_folder
  ensure_identity_project_membership "$IDENTITY_ID"
}

need_command kubectl
need_command curl
need_command jq
need_command infisical
need_command python3
need_command base64

resolve_channel_runtime
wait_for_server
verify_operator_ua_secret
start_port_forward

ADMIN_EMAIL="$(secret_value INFISICAL_AUTO_BOOTSTRAP_EMAIL)"
ADMIN_PASSWORD="$(secret_value INFISICAL_AUTO_BOOTSTRAP_PASSWORD)"
BOOTSTRAP_RESULT="$(bootstrap_or_login "http://127.0.0.1:${LOCAL_PORT}" "$ADMIN_EMAIL" "$ADMIN_PASSWORD")"
ADMIN_TOKEN="${BOOTSTRAP_RESULT%%$'\t'*}"
ORG_ID="${BOOTSTRAP_RESULT#*$'\t'}"
IDENTITY_ID="$(find_identity)"

prepare_project_path "server-manager" "$ENVIRONMENT_SLUG" "/runtime/local"
set_secret_if_absent "DISCORD_BOT_TOKEN" "${DISCORD_BOT_TOKEN:-e2e.synthetic.discord.token}"
set_secret_if_absent "DISCORD_GUILD_ID" "${DISCORD_GUILD_ID:-900000000000000001}"
set_secret_if_absent "SUPABASE_SERVICE_KEY" "${SUPABASE_SERVICE_KEY:-e2e-local-supabase-service-key}"

if [[ -n "${DISCORD_BOT_TOKEN:-}" ]]; then
  log "Infisical project server-manager path /runtime/local is bootstrapped with operator-supplied Discord token"
else
  log "Infisical project server-manager path /runtime/local is bootstrapped with synthetic local Discord token"
fi

prepare_project_path "platform-observability" "local" "/observability/local/grafana"
set_secret_if_absent "GF_SECURITY_ADMIN_USER" "${GRAFANA_ADMIN_USER:-admin}"
set_secret_if_absent "GF_SECURITY_ADMIN_PASSWORD" "${GRAFANA_ADMIN_PASSWORD:-e2e-local-grafana-admin}"
log "Infisical project platform-observability path /observability/local/grafana is bootstrapped"

prepare_project_path "platform-vultr" "dev" "/api"
set_secret_if_absent "credentials" "${VULTR_API_KEY:-e2e-local-vultr-token}"
log "Infisical project platform-vultr path /api is bootstrapped with local credentials placeholder when VULTR_API_KEY is absent"

prepare_project_path "tenant-sample-local" "local" "/runtime"
set_secret_if_absent "TENANT_ID" "sample"
set_secret_if_absent "TENANT_CHANNEL" "local"
log "Infisical project tenant-sample-local path /runtime is bootstrapped"

prepare_project_path "tenant-sample-dev" "local" "/runtime"
set_secret_if_absent "TENANT_ID" "sample"
set_secret_if_absent "TENANT_CHANNEL" "dev"
log "Infisical project tenant-sample-dev path /runtime is bootstrapped"

prepare_project_path "tenant-other-local" "local" "/runtime"
set_secret_if_absent "TENANT_ID" "other"
set_secret_if_absent "TENANT_CHANNEL" "local"
log "Infisical project tenant-other-local path /runtime is bootstrapped"
