#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROUNDTRIP="${REPO_ROOT}/infra/scripts/test-s3-roundtrip.sh"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
PORT="19000"
PORT_FORWARD_PID=""
ROUNDTRIP_TMP_DIR=""
RETAINED_KEY=""
RETAINED_CLEANED_UP=0

usage() {
  cat <<'EOF'
Usage: validate_object_storage_local.sh [--kubeconfig PATH] [--port PORT]

Validates the local INIT-104 object-storage proof against an existing cluster:
MinIO readiness, PVC binding, InfisicalSecret reconciliation, bucket existence,
real S3 PUT/GET/compare/DELETE, and Pod-restart durability.
EOF
}

log() {
  echo "$*"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

stop_port_forward() {
  if [[ -n "${PORT_FORWARD_PID:-}" ]] && kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
}

cleanup_retained_object() {
  if [[ -z "${RETAINED_KEY:-}" || "$RETAINED_CLEANED_UP" -eq 1 ]]; then
    return
  fi

  mc rm "local-minio/humility-local-sample/${RETAINED_KEY}" >/dev/null 2>&1 || true
  RETAINED_CLEANED_UP=1
}

cleanup() {
  cleanup_retained_object
  stop_port_forward
  if [[ -n "${ROUNDTRIP_TMP_DIR:-}" ]]; then
    rm -rf "$ROUNDTRIP_TMP_DIR"
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift
      ;;
    --port)
      [[ $# -ge 2 ]] || die "--port requires a value"
      PORT="$2"
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

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

wait_infisicalsecret_ready() {
  local attempt

  for attempt in $(seq 1 120); do
    if kubectl_cmd -n minio-system get infisicalsecret minio-root -o json 2>/dev/null | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") not in {"secrets.infisical.com/ReadyToSyncSecrets", "Ready"}:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)
raise SystemExit(1)
'; then
      return 0
    fi
    sleep 3
  done

  kubectl_cmd -n minio-system get infisicalsecret minio-root -o yaml || true
  return 1
}

wait_minio_ready_pod() {
  local attempt

  for attempt in $(seq 1 120); do
    if minio_ready_pod >/dev/null; then
      return 0
    fi
    sleep 3
  done

  kubectl_cmd -n minio-system get pods -l app.kubernetes.io/name=minio -o wide || true
  return 1
}

minio_ready_pod() {
  kubectl_cmd -n minio-system get pods -l app.kubernetes.io/name=minio -o json 2>/dev/null | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

for pod in payload.get("items", []):
    if pod.get("metadata", {}).get("deletionTimestamp"):
        continue
    if pod.get("status", {}).get("phase") != "Running":
        continue
    for condition in pod.get("status", {}).get("conditions", []):
        if condition.get("type") == "Ready" and str(condition.get("status")) == "True":
            print(pod.get("metadata", {}).get("name", ""))
            raise SystemExit(0)
raise SystemExit(1)
'
}

secret_key() {
  local key="$1"
  kubectl_cmd -n minio-system get secret minio-root -o "jsonpath={.data.${key}}" | base64 -d
}

start_port_forward() {
  local log_file="${REPO_ROOT}/.tmp/minio-port-forward.log"
  local pod

  mkdir -p "${REPO_ROOT}/.tmp"
  : >"$log_file"
  pod="$(minio_ready_pod)" || die "no Ready MinIO pod available for port-forward"
  [[ -n "$pod" ]] || die "no Ready MinIO pod available for port-forward"
  kubectl_cmd -n minio-system port-forward --address 127.0.0.1 "pod/${pod}" "${PORT}:9000" >"$log_file" 2>&1 &
  PORT_FORWARD_PID="$!"

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PORT}/minio/health/live" >/dev/null 2>&1; then
      return
    fi
    if ! kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
      die "kubectl port-forward exited early; see ${log_file}"
    fi
    sleep 1
  done

  die "MinIO API did not become reachable on localhost:${PORT}; see ${log_file}"
}

mc_alias() {
  local alias_name="$1"
  local access_key="$2"
  local secret_key_value="$3"

  mc alias set "$alias_name" "http://127.0.0.1:${PORT}" "$access_key" "$secret_key_value" >/dev/null
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

require_command kubectl
require_command python3
require_command base64
require_command curl
require_command mc

[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl_cmd get namespace minio-system >/dev/null
log "PASS: Namespace/minio-system exists"

phase="$(kubectl_cmd -n minio-system get pvc minio-data -o jsonpath='{.status.phase}')"
[[ "$phase" == "Bound" ]] || die "PersistentVolumeClaim/minio-data phase is ${phase}"
log "PASS: PersistentVolumeClaim/minio-data Bound"

kubectl_cmd -n minio-system wait deployment/minio --for=condition=Available --timeout=300s >/dev/null
wait_minio_ready_pod
log "PASS: Deployment/minio Available and Pod Ready"

wait_infisicalsecret_ready
log "PASS: InfisicalSecret/minio-root ReadyToSyncSecrets=True"

access_key="$(secret_key MINIO_ROOT_USER)"
secret_key_value="$(secret_key MINIO_ROOT_PASSWORD)"
[[ -n "$access_key" && -n "$secret_key_value" ]] || die "Secret/minio-root has empty credential keys"
log "PASS: Secret/minio-root synced with non-empty keys"

kubectl_cmd -n minio-system wait job/create-sample-bucket --for=condition=Complete --timeout=300s >/dev/null
log "PASS: Job/create-sample-bucket Complete"

start_port_forward
ROUNDTRIP_TMP_DIR="$(mktemp -d)"
tmpdir="$ROUNDTRIP_TMP_DIR"
export MC_CONFIG_DIR="${tmpdir}/mc"
mc_alias local-minio "$access_key" "$secret_key_value"

mc ls local-minio/humility-local-sample >/dev/null
log "PASS: Bucket humility-local-sample exists"

S3_ENDPOINT="http://127.0.0.1:${PORT}" \
S3_ACCESS_KEY_ID="$access_key" \
S3_SECRET_ACCESS_KEY="$secret_key_value" \
S3_REGION="us-east-1" \
S3_BUCKET="humility-local-sample" \
  bash "$ROUNDTRIP"

retained_body="${tmpdir}/retained.txt"
retained_download="${tmpdir}/retained-download.txt"
retained_key="init-104-roundtrip/retained-${$}.txt"
RETAINED_KEY="$retained_key"
printf 'init-104 retained durability sample\n' >"$retained_body"
mc cp "$retained_body" "local-minio/humility-local-sample/${retained_key}" >/dev/null
log "PASS: Retained durability object uploaded"

pod="$(kubectl_cmd -n minio-system get pod -l app.kubernetes.io/name=minio -o jsonpath='{.items[0].metadata.name}')"
kubectl_cmd -n minio-system delete pod "$pod" --wait=false >/dev/null
kubectl_cmd -n minio-system wait deployment/minio --for=condition=Available --timeout=300s >/dev/null
wait_minio_ready_pod
phase="$(kubectl_cmd -n minio-system get pvc minio-data -o jsonpath='{.status.phase}')"
[[ "$phase" == "Bound" ]] || die "PersistentVolumeClaim/minio-data phase after restart is ${phase}"
stop_port_forward
PORT_FORWARD_PID=""
start_port_forward
mc_alias local-minio "$access_key" "$secret_key_value"
mc ls local-minio/humility-local-sample >/dev/null
mc cp "local-minio/humility-local-sample/${retained_key}" "$retained_download" >/dev/null
cmp -s "$retained_body" "$retained_download" || die "retained durability object content mismatch"
cleanup_retained_object
log "PASS: Pod-restart durability verified"
