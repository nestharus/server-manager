#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

CHANNEL="local"
KUBECONFIG_ARG=()
ROTATE=0
LOCAL_PORT="18080"

SERVER_NAMESPACE="infisical-system"
SERVER_DEPLOYMENT="infisical"
POSTGRES_STATEFULSET="postgresql"
REDIS_STATEFULSET="redis-master"
BOOTSTRAP_SECRET_NAME="infisical-server-bootstrap"

ORG_NAME="platform"
PROJECT_SLUG="platform-local"
PROJECT_NAME="platform-local"
ENVIRONMENT_SLUG="local"
ENVIRONMENT_NAME="local"
SECRETS_PATH="/sample"
SAMPLE_SECRET_NAME="INFISICAL_SAMPLE_KEY"
SAMPLE_SECRET_VALUE="infisical-local-ready"
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
  if [[ "${#TEMP_FILES[@]}" -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]}"
  fi
}

trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: bootstrap-infisical-identity.sh [--channel local] [--kubeconfig PATH] [--rotate] [--local-port PORT]

Bootstraps Infisical after the server is Ready:
  - reads the SOPS-applied Secret/infisical-server-bootstrap admin credentials
  - creates or finds project platform-local, environment local, and sample secret
  - creates or finds Machine Identity local-operator with Universal Auth
  - applies Secret/infisical-operator-auth with clientId and clientSecret

The Universal Auth credentials are written only with kubectl apply and are never
written to Git. Re-running is idempotent; --rotate creates and applies a new
clientSecret.
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
      CHANNEL="$2"
      shift
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_ARG=(--kubeconfig "$2")
      shift
      ;;
    --rotate)
      ROTATE=1
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
  kubectl "${KUBECONFIG_ARG[@]}" "$@"
}

json_field() {
  local expression="$1"
  jq -er "$expression"
}

secret_value() {
  local key="$1"
  local value
  value="$(kubectl_cmd -n "$SERVER_NAMESPACE" get secret "$BOOTSTRAP_SECRET_NAME" -o "jsonpath={.data.${key}}" | base64 --decode)"
  [[ -n "$value" ]] || die "Secret/${BOOTSTRAP_SECRET_NAME} key ${key} is empty"
  printf '%s' "$value"
}

resolve_channel_infisical() {
  local resolved
  resolved="$(mktemp)"
  TEMP_FILES+=("$resolved")
  python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$CHANNEL" --out "$resolved" >/dev/null

  PROJECT_SLUG="$(jq -er '.infisical.project_id' "$resolved")"
  PROJECT_NAME="$PROJECT_SLUG"
  ENVIRONMENT_SLUG="$(jq -er '.infisical.environment' "$resolved")"
  ENVIRONMENT_NAME="$ENVIRONMENT_SLUG"
  SECRETS_PATH="$(jq -er '.infisical.secrets_path' "$resolved")"
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
  local log_file="${REPO_ROOT}/.tmp/infisical-port-forward.log"
  mkdir -p "${REPO_ROOT}/.tmp"
  : >"$log_file"
  kubectl_cmd -n "$SERVER_NAMESPACE" port-forward "service/infisical" "127.0.0.1:${LOCAL_PORT}:8080" >"$log_file" 2>&1 &
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
    printf '%s' "$token"
    return
  fi

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
  [[ -n "$token" ]] || die "unable to obtain Infisical admin token from bootstrap or direct login"
  printf '%s' "$token"
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

  set +e
  project="$(api_request GET "/api/v1/projects/slug/${PROJECT_SLUG}")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    printf '%s' "$project" | json_field '.project.id // .id'
    return
  fi
  [[ "$status" -eq 4 ]] || return "$status"

  body="$(jq -n \
    --arg name "$PROJECT_NAME" \
    --arg slug "$PROJECT_SLUG" \
    '{projectName: $name, projectDescription: "Humility local runtime secret project", slug: $slug, template: "default", type: "secret-manager", shouldCreateDefaultEnvs: false, hasDeleteProtection: true}')"
  project="$(api_request POST "/api/v1/projects" "$body")"
  printf '%s' "$project" | json_field '.project.id // .id'
}

ensure_environment() {
  local environments
  local exists
  local body

  environments="$(api_request GET "/api/v1/projects/${PROJECT_ID}/environments")"
  exists="$(jq -er --arg slug "$ENVIRONMENT_SLUG" '.environments[]? | select(.slug == $slug) | .id' <<<"$environments" 2>/dev/null || true)"
  [[ -n "$exists" ]] && return

  body="$(jq -n --arg name "$ENVIRONMENT_NAME" --arg slug "$ENVIRONMENT_SLUG" '{name: $name, slug: $slug, position: 1}')"
  api_request POST "/api/v1/projects/${PROJECT_ID}/environments" "$body" >/dev/null
}

ensure_sample_secret() {
  infisical secrets set "${SAMPLE_SECRET_NAME}=${SAMPLE_SECRET_VALUE}" \
    --domain "http://127.0.0.1:${LOCAL_PORT}/api" \
    --token "$ADMIN_TOKEN" \
    --projectId "$PROJECT_ID" \
    --env "$ENVIRONMENT_SLUG" \
    --path "$SECRETS_PATH" \
    --silent >/dev/null
}

find_or_create_identity() {
  local identities
  local identity_id
  local body

  identities="$(api_request GET "/api/v1/projects/${PROJECT_ID}/identities?limit=1000&search=${IDENTITY_NAME}")"
  identity_id="$(jq -er --arg name "$IDENTITY_NAME" '.identities[]? | select(.name == $name) | .id' <<<"$identities" 2>/dev/null || true)"
  if [[ -n "$identity_id" ]]; then
    printf '%s' "$identity_id"
    return
  fi

  body="$(jq -n --arg name "$IDENTITY_NAME" '{name: $name, hasDeleteProtection: true}')"
  api_request POST "/api/v1/projects/${PROJECT_ID}/identities" "$body" | json_field '.identity.id'
}

ensure_universal_auth() {
  local identity_id="$1"
  local auth
  local client_id
  local body
  local status

  set +e
  auth="$(api_request GET "/api/v1/auth/universal-auth/identities/${identity_id}")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    client_id="$(jq -er '.identityUniversalAuth.clientId // .clientId' <<<"$auth" 2>/dev/null || true)"
    if [[ -n "$client_id" ]]; then
      printf '%s' "$client_id"
      return
    fi
  fi
  [[ "$status" -eq 4 ]] || return "$status"

  body="$(jq -n '{
    clientSecretTrustedIps: [{ipAddress: "0.0.0.0/0"}, {ipAddress: "::/0"}],
    accessTokenTrustedIps: [{ipAddress: "0.0.0.0/0"}, {ipAddress: "::/0"}],
    accessTokenTTL: 7200,
    accessTokenMaxTTL: 7200,
    accessTokenNumUsesLimit: 0,
    accessTokenPeriod: 0,
    lockoutEnabled: true,
    lockoutThreshold: 3,
    lockoutDurationSeconds: 300,
    lockoutCounterResetSeconds: 30
  }')"
  api_request POST "/api/v1/auth/universal-auth/identities/${identity_id}" "$body" | json_field '.identityUniversalAuth.clientId'
}

existing_ua_secret_value() {
  local key="$1"
  kubectl_cmd -n "$UA_SECRET_NAMESPACE" get secret "$UA_SECRET_NAME" -o "jsonpath={.data.${key}}" 2>/dev/null | base64 --decode || true
}

create_client_secret() {
  local identity_id="$1"
  local body

  body="$(jq -n '{description: "Humility local Operator Universal Auth", numUsesLimit: 0, ttl: 0}')"
  api_request POST "/api/v1/auth/universal-auth/identities/${identity_id}/client-secrets" "$body" | json_field '.clientSecret'
}

apply_ua_secret() {
  local client_id="$1"
  local client_secret="$2"

  [[ -n "$client_id" ]] || die "clientId is empty"
  [[ -n "$client_secret" ]] || die "clientSecret is empty"

  kubectl_cmd create namespace "$UA_SECRET_NAMESPACE" --dry-run=client -o yaml | kubectl_cmd apply -f - >/dev/null
  kubectl_cmd -n "$UA_SECRET_NAMESPACE" create secret generic "$UA_SECRET_NAME" \
    --from-literal=clientId="$client_id" \
    --from-literal=clientSecret="$client_secret" \
    --dry-run=client -o yaml | kubectl_cmd apply -f - >/dev/null
}

need_command kubectl
need_command curl
need_command jq
need_command infisical
need_command python3
need_command base64

resolve_channel_infisical
wait_for_server
start_port_forward

ADMIN_EMAIL="$(secret_value INFISICAL_AUTO_BOOTSTRAP_EMAIL)"
ADMIN_PASSWORD="$(secret_value INFISICAL_AUTO_BOOTSTRAP_PASSWORD)"
ADMIN_TOKEN="$(bootstrap_or_login "http://127.0.0.1:${LOCAL_PORT}" "$ADMIN_EMAIL" "$ADMIN_PASSWORD")"

PROJECT_ID="$(find_or_create_project)"
ensure_environment
ensure_sample_secret
IDENTITY_ID="$(find_or_create_identity)"
CLIENT_ID="$(ensure_universal_auth "$IDENTITY_ID")"

CLIENT_SECRET=""
if [[ "$ROTATE" -eq 0 ]]; then
  existing_client_id="$(existing_ua_secret_value clientId)"
  existing_client_secret="$(existing_ua_secret_value clientSecret)"
  if [[ "$existing_client_id" == "$CLIENT_ID" && -n "$existing_client_secret" ]]; then
    CLIENT_SECRET="$existing_client_secret"
  fi
fi

if [[ -z "$CLIENT_SECRET" ]]; then
  CLIENT_SECRET="$(create_client_secret "$IDENTITY_ID")"
fi

apply_ua_secret "$CLIENT_ID" "$CLIENT_SECRET"
log "Applied Secret/${UA_SECRET_NAME} in namespace ${UA_SECRET_NAMESPACE}"
