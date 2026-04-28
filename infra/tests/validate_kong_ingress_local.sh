#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CONTRACT_FIXTURE="${REPO_ROOT}/infra/tests/fixtures/contracts/kong_ingress_contract.yml"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
DNS_IMAGE="${INIT110_DNS_IMAGE:-busybox:1.37.0}"
CURL_IMAGE="${INIT110_CURL_IMAGE:-curlimages/curl:8.16.0}"
STATIC_ONLY=0
KEEP=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TEMP_FILES=()
RESOLVED_JSON=""
KONG_NAMESPACE=""
KONG_DEPLOYMENT=""
KONG_PROXY_SERVICE=""
INGRESS_CLASS=""
SAMPLE_NAMESPACE=""
SAMPLE_NAME=""
SAMPLE_HOST=""
SAMPLE_TLS_SECRET=""
SAMPLE_PROOF_PATH=""
EXPECTED_PROXY_SERVICE_NAME=""

usage() {
  cat <<'EOF'
Usage: validate_kong_ingress_local.sh [--channel local] [--kubeconfig PATH] [--static-only] [--keep]

Validates INIT-110 Kong ingress:
  - channel ingress schema resolution
  - raw Kong chart render and sample ingress kustomize
  - Kong Deployment availability
  - cert-manager TLS Certificate readiness for the sample host
  - cluster DNS resolution for <service>.<channel>.humility.local
  - HTTPS curl through Kong to the backend proof path

Environment:
  INIT110_DNS_IMAGE   Image used for DNS proof Pod (default: busybox:1.37.0)
  INIT110_CURL_IMAGE  Image used for HTTPS proof Pod (default: curlimages/curl:8.16.0)

Options:
  --channel <id>     Channel id to resolve (default: local)
  --kubeconfig PATH  Kubeconfig for the local k3d channel
  --static-only      Skip Kubernetes runtime proof
  --keep             Keep runtime proof Pods after success or failure
  -h, --help         Show this help
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
  if [[ "${#TEMP_FILES[@]}" -gt 0 ]]; then
    for temp_file in "${TEMP_FILES[@]}"; do
      rm -f "$temp_file" >/dev/null 2>&1 || true
    done
  fi

  if [[ "$KEEP" -eq 0 && -n "${KONG_NAMESPACE:-}" && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$KONG_NAMESPACE" delete pod init-110-dns init-110-curl --ignore-not-found >/dev/null 2>&1 || true
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
      --static-only)
        STATIC_ONLY=1
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

json_field() {
  local expression="$1"
  jq -er "$expression" <<<"$RESOLVED_JSON"
}

fixture_field() {
  local expression="$1"
  "$PYTHON_BIN" - "$CONTRACT_FIXTURE" "$expression" <<'PY'
from pathlib import Path
import sys

import yaml

path = Path(sys.argv[1])
value = yaml.safe_load(path.read_text(encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
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
    if python3 -c '
import json
import sys

condition_type = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") != condition_type:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)
raise SystemExit(1)
' "$condition_type" <<<"$payload"
    then
      return 0
    fi
    sleep 3
  done

  echo "Timed out waiting for ${description}" >&2
  return 1
}

assert_file() {
  local path="$1"
  if [[ -f "${REPO_ROOT}/${path}" ]]; then
    pass "exists: ${path}"
  else
    die "missing: ${path}"
  fi
}

assert_channel_contract() {
  local expected_provider
  local expected_ingress_class
  local expected_host
  local expected_proof_path
  local expected_namespace
  local expected_name

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  expected_provider="$(fixture_field local_route.provider)"
  expected_ingress_class="$(fixture_field local_route.ingress_class)"
  expected_host="$(fixture_field local_route.host)"
  expected_proof_path="$(fixture_field backend_health.proof_path)"
  expected_namespace="$(fixture_field local_route.ingress_namespace)"
  expected_name="$(fixture_field local_route.ingress_name)"
  EXPECTED_PROXY_SERVICE_NAME="$(fixture_field local_dns.proxy_service_name)"

  [[ "$(json_field '.ingress.provider')" == "$expected_provider" ]] || die "ingress provider contract"
  [[ "$(json_field '.ingress.ingress_class_name')" == "$expected_ingress_class" ]] || die "ingress class contract"
  [[ "$(json_field '.ingress.proxy_service_name')" == "$EXPECTED_PROXY_SERVICE_NAME" ]] || die "proxy service contract"
  [[ "$(json_field '.ingress.default_service.name')" == "$expected_name" ]] || die "sample route name contract"
  [[ "$(json_field '.ingress.default_service.namespace')" == "$expected_namespace" ]] || die "sample route namespace contract"
  [[ "$(json_field '.ingress.default_service.local_host')" == "$expected_host" ]] || die "local host contract"
  [[ "$(json_field '.ingress.default_service.proof_path')" == "$expected_proof_path" ]] || die "proof path contract"

  KONG_NAMESPACE="$(json_field '.ingress.gateway_namespace')"
  KONG_DEPLOYMENT="$(json_field '.ingress.gateway_deployment_name')"
  KONG_PROXY_SERVICE="$(json_field '.ingress.proxy_service_name')"
  INGRESS_CLASS="$(json_field '.ingress.ingress_class_name')"
  SAMPLE_NAMESPACE="$(json_field '.ingress.default_service.namespace')"
  SAMPLE_NAME="$(json_field '.ingress.default_service.name')"
  SAMPLE_HOST="$(json_field '.ingress.default_service.local_host')"
  SAMPLE_TLS_SECRET="$(json_field '.ingress.default_service.tls_secret_name')"
  SAMPLE_PROOF_PATH="$(json_field '.ingress.default_service.proof_path')"
  pass "resolved channel ingress route contract"
}

assert_static_manifests() {
  local ingress_kustomize
  local local_kustomize

  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

  assert_file "gitops/channels/local/ingress/kong/render-values.yaml"
  assert_file "gitops/channels/local/ingress/default-services/minio/ingress.yaml"
  compgen -G "${REPO_ROOT}/gitops/channels/local/ingress/kong/rendered/*.yaml" >/dev/null \
    || die "missing Kong rendered manifest"
  pass "Kong rendered manifest exists"

  ingress_kustomize="$(mktemp)"
  TEMP_FILES+=("$ingress_kustomize")
  kubectl kustomize "${REPO_ROOT}/gitops/channels/local/ingress" >"$ingress_kustomize"
  pass "ingress raw manifests kustomize"

  local_kustomize="$(mktemp)"
  TEMP_FILES+=("$local_kustomize")
  kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$local_kustomize"
  pass "local root kustomization includes ingress"

  grep -q '^kind: IngressClass$' "$ingress_kustomize" || die "Kong IngressClass rendered"
  grep -q "name: ${EXPECTED_PROXY_SERVICE_NAME}" "$ingress_kustomize" || die "Kong proxy Service rendered"
  grep -q "host: ${SAMPLE_HOST}" "$ingress_kustomize" || die "sample MinIO host rendered"
  pass "Kong and sample ingress objects rendered"
}

assert_runtime() {
  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime proof skipped by --static-only"
    return
  fi
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  kubectl_cmd -n "$KONG_NAMESPACE" wait "deployment/${KONG_DEPLOYMENT}" --for=condition=Available --timeout=300s >/dev/null
  pass "Kong Deployment Available"

  kubectl_cmd get ingressclass "$INGRESS_CLASS" >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" get service "$KONG_PROXY_SERVICE" >/dev/null
  kubectl_cmd -n "$SAMPLE_NAMESPACE" get ingress "$SAMPLE_NAME" >/dev/null
  pass "Kong IngressClass, proxy Service, and sample Ingress exist"

  wait_json_condition \
    "Certificate/${SAMPLE_TLS_SECRET} Ready" \
    "$SAMPLE_NAMESPACE" \
    "certificate/${SAMPLE_TLS_SECRET}" \
    "Ready"
  kubectl_cmd -n "$SAMPLE_NAMESPACE" get secret "$SAMPLE_TLS_SECRET" -o jsonpath='{.data.tls\.crt}' >/dev/null
  pass "Certificate/${SAMPLE_TLS_SECRET} Ready=True and TLS Secret exists"

  kubectl_cmd -n "$KONG_NAMESPACE" delete pod init-110-dns --ignore-not-found >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" wait --for=delete pod/init-110-dns --timeout=60s >/dev/null 2>&1 || true
  kubectl_cmd -n "$KONG_NAMESPACE" run init-110-dns \
    --restart=Never \
    --image="$DNS_IMAGE" \
    --command -- /bin/sh -ec "nslookup ${SAMPLE_HOST}" >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" wait pod/init-110-dns --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" logs init-110-dns | grep -q "$SAMPLE_HOST" || die "DNS lookup did not include ${SAMPLE_HOST}"
  pass "cluster DNS resolves ${SAMPLE_HOST}"

  kubectl_cmd -n "$KONG_NAMESPACE" delete pod init-110-curl --ignore-not-found >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" wait --for=delete pod/init-110-curl --timeout=60s >/dev/null 2>&1 || true
  kubectl_cmd -n "$KONG_NAMESPACE" run init-110-curl \
    --restart=Never \
    --image="$CURL_IMAGE" \
    --command -- /bin/sh -ec "curl -ksS --fail https://${SAMPLE_HOST}${SAMPLE_PROOF_PATH}" >/dev/null
  kubectl_cmd -n "$KONG_NAMESPACE" wait pod/init-110-curl --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null
  pass "curl https://${SAMPLE_HOST}${SAMPLE_PROOF_PATH} through Kong succeeded"
}

main() {
  parse_args "$@"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  command -v jq >/dev/null 2>&1 || die "jq is required"

  assert_channel_contract
  assert_static_manifests
  assert_runtime
  finish
}

main "$@"
