#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

CHANNEL_REQUEST="local"
CHANNEL=""
KUBECONFIG_ARG=()
LOCAL_PORT="18081"

SERVER_NAMESPACE="infisical-system"
SERVER_DEPLOYMENT="infisical-infisical-standalone-infisical"
SERVER_SERVICE="infisical"
POSTGRES_STATEFULSET="postgresql"
REDIS_STATEFULSET="redis-master"
BOOTSTRAP_SECRET_NAME="infisical-server-bootstrap"

ORG_NAME="platform"
PROJECT_SLUG="platform-databases"
PROJECT_NAME="platform-databases"
PROJECT_ID=""
ORG_ID=""
ENVIRONMENT_SLUG="local"
ENVIRONMENT_NAME="local"
SECRETS_PATH="/postgres/local/sample-app"
DB_USERNAME="sample_app"
DB_DATABASE="sample_app"
DB_HOST="sample-app-postgres-rw.sample-app-db.svc.cluster.local"
DB_PORT="5432"
DB_SSL_MODE="${DB_SSL_MODE:-}"
DB_SECRET_NAMESPACE="sample-app-db"
DB_APP_SECRET_NAME="sample-app-postgres-app"
DB_URL_SECRET_NAME="sample-app-postgres-url"
IDENTITY_NAME="local-operator"

UA_SECRET_NAME="infisical-operator-auth"
UA_SECRET_NAMESPACE="infisical-system"
TEMP_FILES=()
PORT_FORWARD_PID=""

stop_port_forward() {
  if [[ -n "${PORT_FORWARD_PID:-}" ]] && kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  stop_port_forward
  if [[ ${#TEMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]+"${TEMP_FILES[@]}"}"
  fi
}

trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: bootstrap-infisical-databases.sh [--channel local] [--kubeconfig PATH] [--local-port PORT]

Bootstraps the local application database runtime secret path after INIT-103:
  - verifies the existing Secret/infisical-operator-auth Universal Auth Secret
  - creates or finds project platform-databases and environment local
  - creates or finds /postgres/local/sample-app
  - seeds database connection fields only if absent
  - grants the existing local-operator Machine Identity access to platform-databases

Database credentials are written only to Infisical. Re-running is idempotent and
leaves existing database passwords unchanged. This script never writes database
credentials to Git.
EOF
}

log() {
  printf '%s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || die "--channel requires a value"
      CHANNEL_REQUEST="$2"
      shift
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_ARG=(--kubeconfig "$2")
      shift
      ;;
    --local-port)
      [[ $# -ge 2 ]] || die "--local-port requires a value"
      LOCAL_PORT="$2"
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

json_field() {
  local expression="$1"
  jq -er "$expression"
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

target_secret_value() {
  local key="$1"
  kubectl_cmd -n "$DB_SECRET_NAMESPACE" get secret "$DB_APP_SECRET_NAME" -o "jsonpath={.data.${key}}" 2>/dev/null | base64 -d || true
}

target_url_secret_value() {
  local key="$1"
  kubectl_cmd -n "$DB_SECRET_NAMESPACE" get secret "$DB_URL_SECRET_NAME" -o "jsonpath={.data.${key}}" 2>/dev/null | base64 -d || true
}

sample_runtime_already_bootstrapped() {
  [[ -n "$(operator_ua_secret_value clientId)" ]] || return 1
  [[ -n "$(operator_ua_secret_value clientSecret)" ]] || return 1
  [[ -n "$(target_secret_value username)" ]] || return 1
  [[ -n "$(target_secret_value password)" ]] || return 1
  [[ -n "$(target_url_secret_value url)" ]] || return 1
}

resolve_channel_databases() {
  local resolved
  resolved="$(mktemp)"
  TEMP_FILES+=("$resolved")
  python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$CHANNEL_REQUEST" --out "$resolved" >/dev/null

  CHANNEL="$(jq -er '.id' "$resolved")"
  PROJECT_SLUG="$(jq -er '.data_plane.credentials.infisical_project' "$resolved")"
  PROJECT_NAME="$PROJECT_SLUG"
  ENVIRONMENT_SLUG="$(jq -er '.data_plane.credentials.infisical_environment' "$resolved")"
  ENVIRONMENT_NAME="$ENVIRONMENT_SLUG"
  SECRETS_PATH="$(jq -er '.data_plane.credentials.infisical_path' "$resolved")"
  DB_USERNAME="$(jq -er '.data_plane.sample.owner' "$resolved")"
  DB_DATABASE="$(jq -er '.data_plane.sample.database' "$resolved")"
  DB_HOST="$(jq -er '.data_plane.sample.service_name + "." + .data_plane.sample.namespace + ".svc.cluster.local"' "$resolved")"
  DB_PORT="5432"
  DB_SECRET_NAMESPACE="$(jq -er '.data_plane.sample.namespace' "$resolved")"
  DB_APP_SECRET_NAME="$(jq -er '.data_plane.credentials.app_secret_name' "$resolved")"
  DB_URL_SECRET_NAME="$(jq -er '.data_plane.credentials.url_secret_name' "$resolved")"
  UA_SECRET_NAME="$(jq -er '.infisical.universal_auth_secret_name' "$resolved")"
  UA_SECRET_NAMESPACE="$(jq -er '.infisical.universal_auth_secret_namespace' "$resolved")"
  SERVER_NAMESPACE="$(jq -er '.infisical.operator_namespace' "$resolved")"

  if [[ -z "$DB_SSL_MODE" ]]; then
    if [[ "$ENVIRONMENT_SLUG" == "local" ]]; then
      DB_SSL_MODE="disable"
    else
      DB_SSL_MODE="require"
    fi
  fi
}

wait_for_server() {
  log "Waiting for Infisical server dependencies in namespace ${SERVER_NAMESPACE}"
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${POSTGRES_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${REDIS_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "deployment/${SERVER_DEPLOYMENT}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" wait "deployment/${SERVER_DEPLOYMENT}" --for=condition=Available --timeout=300s >/dev/null
}

start_port_forward() {
  local log_file="${REPO_ROOT}/.tmp/infisical-databases-port-forward.log"
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

  if [[ -z "${ORG_ID:-}" ]]; then
    set +e
    token="$(
      infisical login \
        --method user \
        --email "$admin_email" \
        --password "$admin_password" \
        --domain "${api_url}/api" \
        --plain \
        --silent 2>/dev/null
    )"
    set -e
    [[ -n "$token" ]] || die "unable to obtain Infisical admin token without organization id"
    printf '%s\t%s' "$token" ""
    return
  fi

  set +e
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
  set -e
  [[ -n "$token" ]] || die "unable to obtain Infisical admin token from bootstrap or direct login"
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
  local status
  local project_id
  local org_id

  set +e
  project="$(api_request GET "/api/v1/projects/slug/${PROJECT_SLUG}")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    project_id="$(jq -er '.project.id // .id' <<<"$project")"
    org_id="$(jq -er '.project.orgId // .orgId' <<<"$project")"
    printf '%s\t%s' "$project_id" "$org_id"
    return
  fi
  [[ "$status" -eq 4 ]] || return "$status"

  body="$(jq -n \
    --arg name "$PROJECT_NAME" \
    --arg slug "$PROJECT_SLUG" \
    '{projectName: $name, projectDescription: "Humility application database runtime secrets", slug: $slug, template: "default", type: "secret-manager", shouldCreateDefaultEnvs: false, hasDeleteProtection: true}')"
  project="$(api_request POST "/api/v1/projects" "$body")"
  project_id="$(jq -er '.project.id // .id' <<<"$project")"
  org_id="$(jq -er '.project.orgId // .orgId' <<<"$project")"
  printf '%s\t%s' "$project_id" "$org_id"
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
  local normalized
  local current="/"
  local segment
  local parent_path
  local encoded_path
  local folders
  local exists
  local body

  normalized="${SECRETS_PATH#/}"
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

    if [[ "$current" == "/" ]]; then
      current="/${segment}"
    else
      current="${current}/${segment}"
    fi
  done
}

find_identity() {
  local identities
  local body

  body="$(jq -n --arg name "$IDENTITY_NAME" '{limit: 100, search: {name: {"$eq": $name}}}')"
  identities="$(api_request POST "/api/v1/identities/search" "$body")" || die "failed to search Infisical identities"
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

secret_value_or_empty() {
  local name="$1"
  local secret_path="${SECRETS_PATH%/}"

  infisical secrets get "$name" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$secret_path" \
    --plain \
    --silent 2>/dev/null || true
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

generate_password() {
  openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n'
}

bootstrap_database_path() {
  local secrets_path="$1"
  local username="$2"
  local database="$3"
  local host="$4"
  local port="$5"
  local ssl_mode="$6"

  SECRETS_PATH="$secrets_path"
  DB_USERNAME="$username"
  DB_DATABASE="$database"
  DB_HOST="$host"
  DB_PORT="$port"
  DB_SSL_MODE="$ssl_mode"

  ensure_secret_folder
  set_secret_if_absent "username" "$DB_USERNAME"
  set_secret_if_absent "database" "$DB_DATABASE"
  set_secret_if_absent "host" "$DB_HOST"
  set_secret_if_absent "port" "$DB_PORT"
  set_secret_if_absent "password" "$(generate_password)"

  DB_PASSWORD="$(secret_value_or_empty password)"
  [[ -n "$DB_PASSWORD" ]] || die "database password was not readable after bootstrap for ${SECRETS_PATH}"
  DB_PASSWORD_ENCODED="$(urlencode "$DB_PASSWORD")"
  set_secret_if_absent "url" "postgres://${DB_USERNAME}:${DB_PASSWORD_ENCODED}@${DB_HOST}:${DB_PORT}/${DB_DATABASE}?sslmode=${DB_SSL_MODE}"

  log "Infisical project ${PROJECT_SLUG} path ${SECRETS_PATH} is bootstrapped for channel ${CHANNEL}"
}

need_command kubectl
need_command curl
need_command jq
need_command infisical
need_command python3
need_command base64
need_command openssl

resolve_channel_databases
wait_for_server
verify_operator_ua_secret
if sample_runtime_already_bootstrapped; then
  log "Infisical database credentials already synced to Secret/${DB_APP_SECRET_NAME} and Secret/${DB_URL_SECRET_NAME}"
fi
start_port_forward

ADMIN_EMAIL="$(secret_value INFISICAL_AUTO_BOOTSTRAP_EMAIL)"
ADMIN_PASSWORD="$(secret_value INFISICAL_AUTO_BOOTSTRAP_PASSWORD)"
BOOTSTRAP_RESULT="$(bootstrap_or_login "http://127.0.0.1:${LOCAL_PORT}" "$ADMIN_EMAIL" "$ADMIN_PASSWORD")"
ADMIN_TOKEN="${BOOTSTRAP_RESULT%%$'\t'*}"
ORG_ID="${BOOTSTRAP_RESULT#*$'\t'}"

PROJECT_RESULT="$(find_or_create_project)"
PROJECT_ID="${PROJECT_RESULT%%$'\t'*}"
PROJECT_ORG_ID="${PROJECT_RESULT#*$'\t'}"
if [[ -n "$PROJECT_ORG_ID" ]]; then
  ORG_ID="$PROJECT_ORG_ID"
fi

ensure_environment
IDENTITY_ID="$(find_identity)"
ensure_identity_project_membership "$IDENTITY_ID"

bootstrap_database_path \
  "$SECRETS_PATH" \
  "$DB_USERNAME" \
  "$DB_DATABASE" \
  "$DB_HOST" \
  "$DB_PORT" \
  "$DB_SSL_MODE"

bootstrap_database_path \
  "/postgres/local/server-manager" \
  "server_manager" \
  "server_manager" \
  "server-manager-postgres-rw.server-manager.svc.cluster.local" \
  "5432" \
  "$DB_SSL_MODE"
