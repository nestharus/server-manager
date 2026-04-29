#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

CHANNEL_REQUEST="local"
KUBECONFIG_ARG=()
LOCAL_PORT="18084"
ROTATE_POMERIUM_SECRETS="false"

SERVER_NAMESPACE="infisical-system"
SERVER_DEPLOYMENT="infisical-infisical-standalone-infisical"
SERVER_SERVICE="infisical"
POSTGRES_STATEFULSET="postgresql"
REDIS_STATEFULSET="redis-master"
BOOTSTRAP_SECRET_NAME="infisical-server-bootstrap"

ORG_NAME="platform"
PROJECT_SLUG="platform-auth"
PROJECT_NAME="platform-auth"
PROJECT_ID=""
ORG_ID=""
ENVIRONMENT_SLUG="local"
ENVIRONMENT_NAME="local"
IDENTITY_NAME="local-operator"
UA_SECRET_NAME="infisical-operator-auth"
UA_SECRET_NAMESPACE="infisical-system"

AUTHENTIK_PATH="/auth/local/authentik"
POMERIUM_PATH="/auth/local/pomerium"
AUTHENTIK_BOOTSTRAP_EMAIL="admin@local.humility.local"
SAMPLE_USER_EMAIL="sample@local.humility.local"

TEMP_FILES=()
PORT_FORWARD_PID=""

usage() {
  cat <<'EOF'
Usage: bootstrap-infisical-auth.sh [--channel local] [--kubeconfig PATH] [--local-port PORT] [--rotate-pomerium-secrets]

Bootstraps INIT-114 local auth secrets:
  - creates or finds Infisical project platform-auth and environment local
  - creates /auth/local/authentik and /auth/local/pomerium folders
  - grants the existing local-operator Machine Identity access to platform-auth
  - seeds missing Authentik and Pomerium credential values only if absent

Credentials are written only to Infisical. Re-running is idempotent and leaves
existing auth secrets unchanged.

Use --rotate-pomerium-secrets only to recover local generated Pomerium crypto
secrets after a failed bootstrap or format bug. It does not modify Authentik
credentials or OIDC client identifiers.
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
      continue
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_ARG=(--kubeconfig "$2")
      shift 2
      continue
      ;;
    --local-port)
      [[ $# -ge 2 ]] || die "--local-port requires a value"
      LOCAL_PORT="$2"
      shift 2
      continue
      ;;
    --rotate-pomerium-secrets)
      ROTATE_POMERIUM_SECRETS="true"
      shift
      continue
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
  if [[ "${#KUBECONFIG_ARG[@]}" -gt 0 ]]; then
    kubectl "${KUBECONFIG_ARG[@]}" "$@"
  else
    kubectl "$@"
  fi
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

resolve_channel_auth() {
  local resolved
  resolved="$(mktemp)"
  TEMP_FILES+=("$resolved")
  python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$CHANNEL_REQUEST" --out "$resolved" >/dev/null

  PROJECT_SLUG="$(jq -er '.auth_stack.authentik.infisical_project' "$resolved")"
  PROJECT_NAME="$PROJECT_SLUG"
  ENVIRONMENT_SLUG="$(jq -er '.auth_stack.authentik.infisical_environment' "$resolved")"
  ENVIRONMENT_NAME="$ENVIRONMENT_SLUG"
  AUTHENTIK_PATH="$(jq -er '.auth_stack.authentik.infisical_path' "$resolved")"
  POMERIUM_PATH="$(jq -er '.auth_stack.pomerium.infisical_path' "$resolved")"
  UA_SECRET_NAME="$(jq -er '.infisical.universal_auth_secret_name' "$resolved")"
  UA_SECRET_NAMESPACE="$(jq -er '.infisical.universal_auth_secret_namespace' "$resolved")"
  SERVER_NAMESPACE="$(jq -er '.infisical.operator_namespace' "$resolved")"
}

wait_for_server() {
  log "Waiting for Infisical server dependencies in namespace ${SERVER_NAMESPACE}"
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${POSTGRES_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "statefulset/${REDIS_STATEFULSET}" --timeout=300s >/dev/null
  kubectl_cmd -n "$SERVER_NAMESPACE" rollout status "deployment/${SERVER_DEPLOYMENT}" --timeout=300s >/dev/null
}

start_port_forward() {
  local log_file="${REPO_ROOT}/.tmp/infisical-auth-port-forward.log"
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

  body="$(jq -n --arg name "$PROJECT_NAME" --arg slug "$PROJECT_SLUG" --arg org_id "$org_id" '{projectName: $name, slug: $slug, organizationId: $org_id}')"
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
  local secret_path="$1"
  local normalized="${secret_path#/}"
  local current="/"
  local segment
  local parent_path
  local folders
  local exists
  local body

  normalized="${normalized%/}"
  [[ -n "$normalized" ]] || return

  IFS='/' read -r -a segments <<<"$normalized"
  for segment in "${segments[@]}"; do
    parent_path="$current"
    folders="$(api_request GET "/api/v2/folders?projectId=${PROJECT_ID}&environment=${ENVIRONMENT_SLUG}&path=${parent_path}&recursive=false")"
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
  local secret_path="$1"
  local name="$2"
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

get_secret() {
  local secret_path="$1"
  local name="$2"
  infisical secrets get "$name" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$secret_path" \
    --plain \
    --silent 2>/dev/null
}

set_secret_if_absent() {
  local secret_path="$1"
  local name="$2"
  local value="$3"

  if secret_exists "$secret_path" "$name"; then
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

set_secret() {
  local secret_path="$1"
  local name="$2"
  local value="$3"

  infisical secrets set "${name}=${value}" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$secret_path" \
    --silent >/dev/null
}

generate_secret() {
  openssl rand -base64 "${1:-48}" | tr '+/' '-_' | tr -d '=\n'
}

generate_standard_base64_secret() {
  openssl rand -base64 "${1:-32}" | tr -d '\n'
}

generate_pomerium_signing_key() {
  openssl ecparam -genkey -name prime256v1 -noout
}

need_command kubectl
need_command curl
need_command jq
need_command infisical
need_command python3
need_command base64
need_command openssl

resolve_channel_auth
wait_for_server
verify_operator_ua_secret
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
ensure_secret_folder "$AUTHENTIK_PATH"
ensure_secret_folder "$POMERIUM_PATH"
IDENTITY_ID="$(find_identity)"
ensure_identity_project_membership "$IDENTITY_ID"

set_secret_if_absent "$AUTHENTIK_PATH" "AUTHENTIK_SECRET_KEY" "$(generate_secret 64)"
set_secret_if_absent "$AUTHENTIK_PATH" "POSTGRES_PASSWORD" "$(generate_secret)"
set_secret_if_absent "$AUTHENTIK_PATH" "AUTHENTIK_BOOTSTRAP_EMAIL" "$AUTHENTIK_BOOTSTRAP_EMAIL"
set_secret_if_absent "$AUTHENTIK_PATH" "AUTHENTIK_BOOTSTRAP_PASSWORD" "$(generate_secret)"
set_secret_if_absent "$AUTHENTIK_PATH" "AUTHENTIK_BOOTSTRAP_TOKEN" "$(generate_secret)"
set_secret_if_absent "$AUTHENTIK_PATH" "SAMPLE_USER_EMAIL" "$SAMPLE_USER_EMAIL"
set_secret_if_absent "$AUTHENTIK_PATH" "SAMPLE_USER_PASSWORD" "$(generate_secret)"
set_secret_if_absent "$AUTHENTIK_PATH" "DISCORD_APPLICANT_OAUTH_CLIENT_ID" "${DISCORD_APPLICANT_OAUTH_CLIENT_ID:-local-discord-applicant-client-id}"
set_secret_if_absent "$AUTHENTIK_PATH" "DISCORD_APPLICANT_OAUTH_CLIENT_SECRET" "${DISCORD_APPLICANT_OAUTH_CLIENT_SECRET:-local-discord-applicant-client-secret}"
set_secret_if_absent "$AUTHENTIK_PATH" "APPLICANT_OIDC_CLIENT_ID" "${APPLICANT_OIDC_CLIENT_ID:-humility-local-server-manager-applicant}"
set_secret_if_absent "$AUTHENTIK_PATH" "APPLICANT_OIDC_CLIENT_SECRET" "${APPLICANT_OIDC_CLIENT_SECRET:-$(generate_secret)}"
set_secret_if_absent "$AUTHENTIK_PATH" "APPLICANT_RECEIPT_SIGNING_KEY" "${APPLICANT_RECEIPT_SIGNING_KEY:-$(generate_secret 48)}"

set_secret_if_absent "$POMERIUM_PATH" "OIDC_CLIENT_ID" "humility-local-pomerium"
set_secret_if_absent "$POMERIUM_PATH" "OIDC_CLIENT_SECRET" "$(generate_secret)"
if [[ "$ROTATE_POMERIUM_SECRETS" == "true" ]]; then
  set_secret "$POMERIUM_PATH" "SHARED_SECRET" "$(generate_standard_base64_secret 32)"
  set_secret "$POMERIUM_PATH" "COOKIE_SECRET" "$(generate_standard_base64_secret 32)"
  set_secret "$POMERIUM_PATH" "SIGNING_KEY" "$(generate_pomerium_signing_key)"
else
  set_secret_if_absent "$POMERIUM_PATH" "SHARED_SECRET" "$(generate_standard_base64_secret 32)"
  set_secret_if_absent "$POMERIUM_PATH" "COOKIE_SECRET" "$(generate_standard_base64_secret 32)"
  set_secret_if_absent "$POMERIUM_PATH" "SIGNING_KEY" "$(generate_pomerium_signing_key)"
fi

# Mirror OIDC_CLIENT_ID/SECRET into the Authentik path so the Authentik
# blueprint runner reads matching values from authentik-config and creates
# the OAuth2 Provider + Application that Pomerium expects at
# https://auth.local.humility.local/application/o/pomerium/.
POMERIUM_OIDC_CLIENT_ID="$(get_secret "$POMERIUM_PATH" "OIDC_CLIENT_ID")"
POMERIUM_OIDC_CLIENT_SECRET="$(get_secret "$POMERIUM_PATH" "OIDC_CLIENT_SECRET")"
set_secret "$AUTHENTIK_PATH" "OIDC_CLIENT_ID" "$POMERIUM_OIDC_CLIENT_ID"
set_secret "$AUTHENTIK_PATH" "OIDC_CLIENT_SECRET" "$POMERIUM_OIDC_CLIENT_SECRET"

log "Infisical project ${PROJECT_SLUG} auth paths are bootstrapped for channel ${CHANNEL_REQUEST}"
