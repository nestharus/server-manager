#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILDER="${REPO_ROOT}/infra/scripts/build-server-manager-images.sh"
CONTRACT_FIXTURE="${REPO_ROOT}/infra/tests/fixtures/contracts/application_workloads_contract.yml"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
IMAGE_TAG="init-113-local"
STATIC_ONLY=0
SKIP_IMAGE_BUILD=0
KEEP=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: validate_application_workloads_local.sh [--channel local] [--kubeconfig PATH] [--tag TAG] [--static-only] [--skip-image-build] [--keep]

Validates INIT-113 application workloads:
  - app containerfiles and INIT-108 image wrapper
  - local GitOps application manifests
  - CNPG, Atlas guard, Alembic migration job, Infisical, MinIO bucket, Kong ingress
  - optional local runtime proof: images built, API Ready, DB connected, ingress 200, Discord Pod up

Options:
  --channel <id>       Channel id to resolve (default: local)
  --kubeconfig PATH    Kubeconfig for the local k3d channel
  --tag TAG            Image tag for both app images
  --static-only        Skip Docker and Kubernetes runtime proof
  --skip-image-build   Do not build images before runtime checks
  --keep               Keep runtime proof curl Pod after success or failure
  -h, --help           Show this help
EOF
}

pass() {
  echo "PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "FAIL: $1" >&2
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "SKIP: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

finish() {
  echo "RESULT: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
}

die() {
  fail "$*"
  finish
  exit 1
}

cleanup() {
  local temp_file
  for temp_file in "${TEMP_FILES[@]:-}"; do
    rm -f "$temp_file" >/dev/null 2>&1 || true
  done
  if [[ "$KEEP" -eq 0 && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager delete pod init-113-api-health --ignore-not-found >/dev/null 2>&1 || true
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n kong-system delete pod init-113-api-curl --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

parse_args() {
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
        KUBECONFIG_PATH="$2"
        shift 2
        continue
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift 2
        continue
        ;;
      --static-only)
        STATIC_ONLY=1
        ;;
      --skip-image-build)
        SKIP_IMAGE_BUILD=1
        ;;
      --keep)
        KEEP=1
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

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

fixture_value() {
  local expression="$1"
  "$PYTHON_BIN" - "$CONTRACT_FIXTURE" "$expression" <<'PY'
import sys
from pathlib import Path

import yaml

payload = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

assert_file() {
  local path="$1"
  [[ -f "${REPO_ROOT}/${path}" ]] && pass "exists: ${path}" || die "missing: ${path}"
}

assert_executable() {
  local path="$1"
  [[ -x "${REPO_ROOT}/${path}" ]] && pass "executable: ${path}" || die "not executable: ${path}"
}

assert_static_files() {
  assert_file "containers/server-manager/Containerfile.api"
  assert_file "containers/server-manager/Containerfile.discord"
  assert_executable "infra/scripts/build-server-manager-images.sh"
  assert_file "gitops/channels/local/applications/kustomization.yaml"
  assert_file "gitops/channels/local/applications/server-manager/kustomization.yaml"
  assert_file "gitops/channels/local/applications/server-manager/postgres-cluster.yaml"
  assert_file "gitops/channels/local/applications/server-manager/alembic-migration-job.yaml"
  assert_file "gitops/channels/local/applications/server-manager/api-deployment.yaml"
  assert_file "gitops/channels/local/applications/server-manager/discord-deployment.yaml"
  assert_file "gitops/channels/local/applications/server-manager/api-ingress.yaml"
  assert_file "gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml"
  assert_file "gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml"
}

assert_kustomize() {
  local app_render
  local local_render
  local api_image
  local discord_image
  local ingress_host

  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for kustomize validation"
  api_image="$(fixture_value images.api)"
  discord_image="$(fixture_value images.discord)"
  ingress_host="$(fixture_value ingress.host)"

  app_render="$(mktemp)"
  local_render="$(mktemp)"
  TEMP_FILES+=("$app_render" "$local_render")

  kubectl kustomize "${REPO_ROOT}/gitops/channels/local/applications/server-manager" >"$app_render"
  pass "server-manager application kustomize"

  kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$local_render"
  pass "local root kustomization includes applications"

  grep -q 'name: server-manager-postgres' "$app_render" || die "server-manager CNPG Cluster rendered"
  grep -q 'name: server-manager-alembic-migrate' "$app_render" || die "server-manager Alembic Job rendered"
  grep -q "host: ${ingress_host}" "$app_render" || die "server-manager API ingress rendered"
  grep -q "$api_image" "$app_render" || die "server-manager API image rendered"
  grep -q "$discord_image" "$app_render" || die "server-manager Discord image rendered"
  pass "server-manager workload resources rendered"

  grep -q 'name: public-intake-rate-limit' "$app_render" || die "public intake KongPlugin rendered"
  grep -q 'name: server-manager-public-intake-api' "$app_render" || die "public intake API ingress rendered"
  grep -q 'konghq.com/plugins: public-intake-rate-limit' "$app_render" || die "public intake API ingress plugin annotation rendered"
  grep -q 'path: /api/v1/public/applications' "$app_render" || die "public intake API ingress path rendered"
  grep -q 'name: web-public-intake' "$local_render" || die "public intake web ingress rendered"
  grep -q 'path: /api/public/applications' "$local_render" || die "public intake web ingress path rendered"
  pass "public intake rate-limit resources rendered"
}

assert_no_secret_literals() {
  if rg -n '(DISCORD_BOT_TOKEN|SUPABASE_SERVICE_KEY|MINIO_ROOT_PASSWORD|S3_SECRET_ACCESS_KEY):[[:space:]]+[^"{[:space:]]' \
    "${REPO_ROOT}/gitops/channels/local/applications/server-manager" >/tmp/init113-secret-literals.txt; then
    cat /tmp/init113-secret-literals.txt >&2
    die "no committed server-manager credential literals"
  fi
  pass "no committed server-manager credential literals"
}

assert_image_print_only() {
  local output
  output="$("$BUILDER" --channel "$CHANNEL_REQUEST" --tag "$IMAGE_TAG" --print-only)"
  grep -q "PUSH_IMAGE=localhost:5000/local/server-manager-api:${IMAGE_TAG}" <<<"$output" || die "API push image resolves"
  grep -q "PULL_IMAGE=k3d-humility-local:5000/local/server-manager-api:${IMAGE_TAG}" <<<"$output" || die "API pull image resolves"
  grep -q "PUSH_IMAGE=localhost:5000/local/server-manager-discord:${IMAGE_TAG}" <<<"$output" || die "Discord push image resolves"
  grep -q "PULL_IMAGE=k3d-humility-local:5000/local/server-manager-discord:${IMAGE_TAG}" <<<"$output" || die "Discord pull image resolves"
  pass "server-manager image names resolve through INIT-108 builder"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

wait_json_condition() {
  local description="$1"
  local namespace="$2"
  local resource="$3"
  local condition_type="$4"
  local attempts="${5:-120}"
  local attempt
  local payload

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    payload="$(kubectl_cmd -n "$namespace" get "$resource" -o json 2>/dev/null || true)"
    if "$PYTHON_BIN" -c '
import json
import sys

condition_type = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") == condition_type and str(condition.get("status")) == "True":
        raise SystemExit(0)
raise SystemExit(1)
' "$condition_type" <<<"$payload"; then
      return 0
    fi
    sleep 3
  done

  kubectl_cmd -n "$namespace" get "$resource" -o yaml || true
  die "${description} did not report ${condition_type}=True"
}

restricted_pod_overrides() {
  local container_name="$1"
  local image="$2"
  shift 2
  "$PYTHON_BIN" - "$container_name" "$image" "$@" <<'PY'
import json
import sys

container_name = sys.argv[1]
image = sys.argv[2]
command = sys.argv[3:]
container = {
    "name": container_name,
    "image": image,
    "securityContext": {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "runAsNonRoot": True,
        "runAsGroup": 1000,
        "runAsUser": 1000,
    },
}
if command:
    container["command"] = command
print(json.dumps({
    "apiVersion": "v1",
    "spec": {
        "securityContext": {
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        "containers": [container],
    },
}))
PY
}

run_image_build() {
  if [[ "$SKIP_IMAGE_BUILD" -eq 1 ]]; then
    skip "image build skipped by --skip-image-build"
    return
  fi
  command -v docker >/dev/null 2>&1 || die "docker is required for runtime image build"
  docker info >/dev/null 2>&1 || die "docker daemon is unavailable"
  "$BUILDER" --channel "$CHANNEL_REQUEST" --tag "$IMAGE_TAG"
  pass "server-manager API and Discord images built and pushed"
}

assert_runtime() {
  local primary_pod
  local url
  local health_body

  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime proof skipped by --static-only"
    return
  fi
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  run_image_build

  wait_json_condition "Cluster/server-manager-postgres" "server-manager" "cluster/server-manager-postgres" "Ready" 180
  pass "PG Cluster/server-manager-postgres Ready=True"

  kubectl_cmd -n server-manager wait job/server-manager-alembic-migrate --for=condition=Complete --timeout=300s >/dev/null
  pass "Alembic migration Job complete"

  kubectl_cmd -n server-manager rollout status deployment/server-manager-api --timeout=300s >/dev/null
  pass "API Deployment Available"

  primary_pod="$(kubectl_cmd -n server-manager get pods -l 'cnpg.io/cluster=server-manager-postgres,role=primary' -o jsonpath='{.items[0].metadata.name}')"
  url="$(kubectl_cmd -n server-manager get secret server-manager-postgres-url -o jsonpath='{.data.url}' | base64 -d)"
  kubectl_cmd -n server-manager exec "$primary_pod" -c postgres -- psql "$url" -v ON_ERROR_STOP=1 -c "select 1;" >/dev/null
  pass "db connected through server-manager-postgres-rw"

  kubectl_cmd -n server-manager delete pod init-113-api-health --ignore-not-found >/dev/null
  kubectl_cmd -n server-manager wait --for=delete pod/init-113-api-health --timeout=60s >/dev/null 2>&1 || true
  kubectl_cmd -n server-manager run init-113-api-health \
    --rm -i --restart=Never \
    --overrides="$(restricted_pod_overrides init-113-api-health curlimages/curl:8.16.0 curl -fsS http://server-manager-api.server-manager.svc.cluster.local:8000/api/v1/health)" \
    --image=curlimages/curl:8.16.0 >/tmp/init113-api-health.json
  health_body="$(cat /tmp/init113-api-health.json)"
  grep -q '"status":"alive"' <<<"$health_body" || die "API health endpoint returned alive"
  pass "API health endpoint returned alive"

  kubectl_cmd -n kong-system delete pod init-113-api-curl --ignore-not-found >/dev/null
  kubectl_cmd -n kong-system wait --for=delete pod/init-113-api-curl --timeout=60s >/dev/null 2>&1 || true
  kubectl_cmd -n kong-system run init-113-api-curl \
    --restart=Never \
    --overrides="$(restricted_pod_overrides init-113-api-curl curlimages/curl:8.16.0 /bin/sh -ec "curl -ksS --fail https://api.local.humility.local/api/v1/health")" \
    --image=curlimages/curl:8.16.0 >/dev/null
  kubectl_cmd -n kong-system wait pod/init-113-api-curl --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null
  pass "ingress curl https://api.local.humility.local/api/v1/health returned 200"

  kubectl_cmd -n server-manager rollout status deployment/server-manager-discord --timeout=300s >/dev/null
  kubectl_cmd -n server-manager get pods -l app.kubernetes.io/name=server-manager-discord -o name | grep -q .
  pass "Discord Deployment Available and Pod exists"
}

main() {
  parse_args "$@"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  command -v rg >/dev/null 2>&1 || die "rg is required"

  assert_static_files
  assert_kustomize
  assert_no_secret_literals
  assert_image_print_only
  assert_runtime
  finish
}

main "$@"
